import seaborn as sns
import folium
from streamlit_folium import st_folium, folium_static
import osmnx as ox
import streamlit as st
import pydeck as pdk
import base64
from PIL import Image
import io


st.set_page_config(layout='wide')


hide_menu_style = """
        <style>
            [data-testid="stSidebar"]{
            min-width: 0px;
            max-width: 200px;
            }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        </style>
        """
st.markdown(hide_menu_style, unsafe_allow_html=True)


st.title("Sensory Map")
st.subheader("North End, Boston")


# Parse the output.txt file
# locations = []
# with open('./resized_photos/output.txt', 'r') as file:
#     lines = file.readlines()
#     i = 0
#     while i < len(lines) - 3:  # leave some room for the last few lines
#         # Skip summary lines
#         if "image files read" in lines[i] or "directories scanned" in lines[i]:
#             break
#         # Strip out the '======== ' part and ensure it's a file path (simple check)
#         filename = lines[i].replace("======== ", "").strip()
#         if not filename.startswith('./'):
#             i += 1
#             continue
#         try:
#             lat = float(lines[i+1].split(':')[-1].strip())
#             lon = float(lines[i+2].split(':')[-1].strip())
#             date = lines[i+3].split(': ')[-1].strip()  # Extract the date
#             locations.append(
#                 {'filename': filename, 'lat': lat, 'lon': lon, 'date': date})
#         except ValueError:  # handle any parsing errors and continue
#             st.write(f"Error processing line {i}: {lines[i]}")
#         i += 4

def read_metadata(file_path, is_video=False):
    locations = []
    with open(file_path, 'r') as file:
        lines = file.readlines()
        i = 0
        while i < len(lines):
            if "image files read" in lines[i] or "directories scanned" in lines[i]:
                break
            filename = lines[i].replace("======== ", "").strip()
            lat = float(lines[i+1].split(':')[-1].strip())
            lon = float(lines[i+2].split(':')[-1].strip())
            date = None if is_video else lines[i+3].split(': ')[-1].strip()
            locations.append({'filename': filename, 'lat': lat, 'lon': lon,
                             'date': date, 'type': 'video' if is_video else 'image'})
            i += 3 if is_video else 4
    return locations


image_locations = read_metadata('./resized_photos/output.txt', is_video=False)
video_locations = read_metadata('./resized_videos/output.txt', is_video=True)

all_locations = image_locations + video_locations


def determine_file_type(filename):
    """Determine whether the filename refers to an image or a video."""
    image_exts = ['.jpg']
    video_exts = ['.mov']

    if any(filename.lower().endswith(ext) for ext in image_exts):
        return 'image'
    elif any(filename.lower().endswith(ext) for ext in video_exts):
        return 'video'
    else:
        return 'unknown'


# Create the map
# retrieve the network
G = ox.graph_from_place("North End, Boston", network_type="all")
# convert the graph to a folium map
graph_map = ox.plot_graph_folium(
    G, popup_attribute='name', color="gray", weight=2, opacity=0.5)
# add a tile layer to the folium map
# tile_layer = folium.TileLayer('OpenStreetMap').add_to(graph_map)


def image_to_base64(img_path):
    """Converts an image file to base64."""
    with open(img_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode()


# st.video("./resized_videos/IMG_7907.mp4")

# Add markers for each location with media popups
for loc in all_locations:
    # Determine the marker color based on the type
    marker_color = 'cornflowerblue' if loc['type'] == 'video' else 'lightcoral'

    # Generate the media_html based on the type
    if loc['type'] == 'image':
        encoded_media = image_to_base64(
            loc["filename"].replace("./", "./resized_photos/"))
        media_html = f'<img src="data:image/jpeg;base64,{encoded_media}" width="200">'
    elif loc['type'] == 'video':
        video_path = loc["filename"].replace(
            "./", "./resized_videos/").replace(".MOV", ".mp4")
        #media_html = f'<a href="{video_path}" target="_blank">View Video</a>'
        media_html = f'<video width="200" controls><source src="{video_path}" type="video/mp4">Your browser does not support the video tag.</video>'

    else:
        continue  # skip unknown types

    # If there's a date associated, append it to the media_html
    if loc.get('date'):
        media_html += f'<br>{loc["date"]}'

    # Create the popup
    popup = folium.Popup(media_html, max_width=2650)

    folium.CircleMarker(
        location=(loc["lat"], loc["lon"]),
        popup=popup,
        radius=18,
        color='',
        fill=True,
        fill_color=marker_color
    ).add_to(graph_map)


folium_static(graph_map, width=1200, height=800)
