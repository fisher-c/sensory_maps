from __future__ import annotations

import base64
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import folium
import streamlit as st
from streamlit_folium import st_folium


st.set_page_config(layout="wide", initial_sidebar_state="collapsed")


hide_menu_style = """
        <style>
        /* Tighter, cleaner overall layout */
        section.main > div { padding-top: 0.1rem; padding-bottom: 0.1rem; }
        [data-testid="stAppViewContainer"] { background: #ffffff; }
        /* Reduce horizontal whitespace between columns */
        div[data-testid="stHorizontalBlock"] { gap: 0.1rem !important; }

            [data-testid="stSidebar"]{
            min-width: 0px;
            max-width: 300px;
            }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        </style>
        """
st.markdown(hide_menu_style, unsafe_allow_html=True)


st.markdown(
    """
    <div style="display:flex; align-items:baseline; gap:0.75rem; flex-wrap:wrap;">
      <h2 style="margin:0; line-height:1.1;">Sensory Map</h2>
      <span style="opacity:0.7; font-size:1.05rem;">North End, Boston</span>
    </div>
    """,
    unsafe_allow_html=True,
)



REPO_ROOT = Path(__file__).resolve().parent
PHOTOS_DIR = REPO_ROOT / "resized_photos"
VIDEOS_DIR = REPO_ROOT / "resized_videos"
CACHE_DIR = REPO_ROOT / "cache"
LIKES_PATH = CACHE_DIR / "likes.json"
# Change this to any CSS color (e.g. "#14b8a6", "goldenrod", "rebeccapurple").
LIKED_COLOR = "#14b8a6"


@dataclass(frozen=True)
class Location:
    filename: str
    lat: float
    lon: float
    date: Optional[str]
    media_type: str  # "image" | "video"

    @property
    def display_label(self) -> str:
        date_part = f" — {self.date}" if self.date else ""
        return f"{self.media_type}: {self.filename}{date_part}"


def _parse_float_after_colon(line: str) -> Optional[float]:
    if ":" not in line:
        return None
    try:
        return float(line.split(":", 1)[1].strip())
    except ValueError:
        return None


def _parse_str_after_colon(line: str) -> Optional[str]:
    if ":" not in line:
        return None
    value = line.split(":", 1)[1].strip()
    return value or None


def read_metadata(txt_path: Path, media_type: str) -> list[Location]:
    if not txt_path.exists():
        st.warning(f"Missing metadata file: `{txt_path}`")
        return []

    locations: list[Location] = []
    lines = txt_path.read_text(encoding="utf-8", errors="replace").splitlines()

    current_filename: Optional[str] = None
    current_lat: Optional[float] = None
    current_lon: Optional[float] = None
    current_date: Optional[str] = None

    def flush() -> None:
        nonlocal current_filename, current_lat, current_lon, current_date
        if current_filename is None or current_lat is None or current_lon is None:
            current_filename = None
            current_lat = None
            current_lon = None
            current_date = None
            return
        locations.append(
            Location(
                filename=current_filename,
                lat=current_lat,
                lon=current_lon,
                date=current_date if media_type == "image" else None,
                media_type=media_type,
            )
        )
        current_filename = None
        current_lat = None
        current_lon = None
        current_date = None

    for line in lines:
        if "directories scanned" in line or "image files read" in line:
            break

        if line.startswith("========"):
            flush()
            raw_path = line.replace("========", "", 1).strip()
            current_filename = Path(raw_path).name
            continue

        if "GPS Latitude" in line:
            current_lat = _parse_float_after_colon(line)
            continue

        if "GPS Longitude" in line:
            current_lon = _parse_float_after_colon(line)
            continue

        if media_type == "image" and "Date/Time Original" in line:
            current_date = _parse_str_after_colon(line)
            continue

    flush()
    return locations


image_locations = read_metadata(PHOTOS_DIR / "output.txt", media_type="image")
video_locations = read_metadata(VIDEOS_DIR / "output.txt", media_type="video")

all_locations: list[Location] = image_locations + video_locations


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _nearest_locations(
    locations: Iterable[Location], lat: float, lon: float, max_meters: float
) -> list[Location]:
    ranked = sorted(
        ((loc, _haversine_m(lat, lon, loc.lat, loc.lon)) for loc in locations),
        key=lambda x: x[1],
    )
    return [loc for loc, d in ranked if d <= max_meters]


def resolve_media_path(loc: Location) -> Path:
    if loc.media_type == "image":
        return PHOTOS_DIR / loc.filename
    base = Path(loc.filename).with_suffix(".mp4").name
    return VIDEOS_DIR / base


def thumbnail_to_base64(img_path: Path, max_bytes: int = 200_000) -> Optional[str]:
    if not img_path.exists():
        return None
    data = img_path.read_bytes()
    if len(data) > max_bytes:
        return None
    return base64.b64encode(data).decode("ascii")

@st.cache_data(show_spinner=False)
def _file_to_base64(path: str, mtime_ns: int) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def _load_likes() -> set[str]:
    try:
        if not LIKES_PATH.exists():
            return set()
        data = json.loads(LIKES_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {str(x) for x in data}
    except Exception:
        return set()
    return set()


def _save_likes(likes: set[str]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        LIKES_PATH.write_text(
            json.dumps(sorted(likes), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        return


if "likes" not in st.session_state:
    st.session_state["likes"] = _load_likes()

likes: set[str] = st.session_state["likes"]


with st.sidebar:
    st.header("Filters")
    show_photos = st.checkbox("Photos", value=True)
    show_videos = st.checkbox("Videos", value=True)
    max_pick_distance_m = st.slider(
        "Click radius (meters)", min_value=5, max_value=100, value=25, step=5
    )
    popup_thumbnails = st.checkbox(
        "Show image thumbnails in popups (slower)", value=False
    )
    st.caption(f"❤️ Liked: {len(likes)}")

filtered_locations = [
    loc
    for loc in all_locations
    if (show_photos and loc.media_type == "image")
    or (show_videos and loc.media_type == "video")
]

if not filtered_locations:
    st.info("No locations to show with the current filters.")

center_lat = 42.363
center_lon = -71.055

m = folium.Map(
    location=(center_lat, center_lon),
    zoom_start=15,
    tiles="CartoDB positron", #"OpenStreetMap",
    control_scale=True,
)

photos_group = folium.FeatureGroup(name="Photos", show=show_photos)
videos_group = folium.FeatureGroup(name="Videos", show=show_videos)

for loc in filtered_locations:
    is_liked = loc.media_type == "image" and loc.filename in likes
    marker_color = (
        LIKED_COLOR
        if is_liked
        else ("cornflowerblue" if loc.media_type == "video" else "lightcoral")
    )

    heart = " ❤️" if is_liked else ""
    popup_lines = [f"<b>{loc.media_type.title()}</b>{heart} — {loc.filename}"]
    if loc.date:
        popup_lines.append(f"<br>{loc.date}")

    if popup_thumbnails and loc.media_type == "image":
        encoded = thumbnail_to_base64(resolve_media_path(loc))
        if encoded:
            popup_lines.append(
                f'<br><img src="data:image/jpeg;base64,{encoded}" width="180">'
            )

    popup = folium.Popup("".join(popup_lines), max_width=400)
    marker = folium.CircleMarker(
        location=(loc.lat, loc.lon),
        popup=popup,
        radius=12 if is_liked else 10,
        color="",
        fill=True,
        fill_color=marker_color,
        fill_opacity=0.85,
    )

    if loc.media_type == "image":
        marker.add_to(photos_group)
    else:
        marker.add_to(videos_group)

photos_group.add_to(m)
videos_group.add_to(m)
folium.LayerControl(collapsed=True).add_to(m)

left, right = st.columns([6, 3], gap="small")

with left:
    map_state = st_folium(m, height=640, use_container_width=True, key="sensory_map")

with right:
    with st.container(height=640):
        st.markdown("##### Selected")
        selected: Optional[Location] = None
        state = map_state or {}
        clicked = state.get("last_object_clicked") or state.get("last_clicked")
        if clicked and "lat" in clicked and ("lng" in clicked or "lon" in clicked):
            clicked_lat = float(clicked["lat"])
            clicked_lon = float(clicked.get("lng", clicked.get("lon")))
            candidates = _nearest_locations(
                filtered_locations,
                lat=clicked_lat,
                lon=clicked_lon,
                max_meters=float(max_pick_distance_m),
            )
            if candidates:
                if len(candidates) == 1:
                    selected = candidates[0]
                else:
                    selected = st.selectbox(
                        "Multiple media here",
                        options=candidates,
                        format_func=lambda l: l.display_label,
                        key=f"selected_location_{clicked_lat:.6f}_{clicked_lon:.6f}",
                    )

        if selected is None:
            st.caption("Click a marker to preview the photo/video here.")
        else:
            media_path = resolve_media_path(selected)
            if not media_path.exists():
                st.error(f"File not found: `{media_path}`")
            elif selected.media_type == "image":
                is_liked = selected.filename in likes
                try:
                    stat = media_path.stat()
                    encoded = _file_to_base64(str(media_path), stat.st_mtime_ns)
                    st.markdown(
                        f"""
                        <div style="width:100%; height:460px; margin-top:0.25rem; margin-bottom:0.25rem;">
                          <img
                            src="data:image/jpeg;base64,{encoded}"
                            style="width:100%; height:100%; object-fit:cover; border-radius:12px; display:block;"
                          />
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                except Exception:
                    st.image(
                        str(media_path),
                        use_container_width=True,
                    )
                st.caption(selected.date or selected.filename)
                if st.button(
                    "💔 Unlike" if is_liked else "♡ Like",
                    use_container_width=True,
                    key=f"like_{selected.filename}",
                ):
                    if is_liked:
                        likes.discard(selected.filename)
                    else:
                        likes.add(selected.filename)
                    _save_likes(likes)
                    st.rerun()
            else:
                st.video(str(media_path))
