#!/usr/bin/env python3

from flask import Flask, request, jsonify
import requests
import tempfile
import os
import re

# global variables
TMDB_API_KEY = "TMDB_API_KEY"
LANGUAGE = "fr-FR"
LANGUAGE2 = "en-US"
base_url = "https://api.themoviedb.org/3"
WHATSAPP_API_URL = "http://10.10.66.200:3000" # internal docker subnet ip
WHATSAPP_NUMBER = "<phone-number>@s.whatsapp.net" # Or for a group: "<group-number>@g.us"
WHATSAPP_API_USERNAME = "johnsmith"
WHATSAPP_API_PWD = "S3cR3t!"

app = Flask(__name__)

# function to send to whatsapp API
def send_whatsapp(phone, message, send_image=False, picture_path=None):
    # WhatsApp API Parameters
    url = f"{WHATSAPP_API_URL}/send/image" if send_image else f"{WHATSAPP_API_URL}/send/message"
    auth = (WHATSAPP_API_USERNAME, WHATSAPP_API_PWD)

    # WhatsApp API Headers
    headers = {'accept': 'application/json'}

    # WhatsApp API Data
    data = {'phone': phone}

    if send_image:
        # Send Image
        data['caption'] = message
        data['compress'] = "True"
        files = {'image': ('image', open(picture_path, 'rb'), 'image/png')}
    else:
        # Send Message
        data['message'] = message

    # Send the message to WhatsApp API
    response = requests.post(url, headers=headers, data=data, auth=auth, files=files if send_image else None)
    return response

def format_message(title, requestedBy_username, overview, media_link, trailer=False):
  message = f"*{title}*\n"
  
  message += f"  → ajouté par {requestedBy_username}\n"
  
  if overview:
    message += f"```{overview}```\n"
  
  message += f"{media_link}\n"
  
  if trailer:
    message += trailer

  return message

def download_and_get_poster_by_id(poster_id):
    poster_url = f"https://image.tmdb.org/t/p/w342/{poster_id}"
    
    # Download and save poster to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp:
        response = requests.get(poster_url)
        temp.write(response.content)
        temp_path = temp.name

    return temp_path

def get_tmdb_details(media_type, tmdbid, language=LANGUAGE):
    # get details from tmdb API
    url = f"{base_url}/{media_type}/{tmdbid}"
    params = {
        'api_key': TMDB_API_KEY,
        'language': language,
    }
    response = requests.get(url, params=params, timeout=10)
    return response.json()

def get_trailer_link(media_type, tmdbid):
    # parameters
    global TMDB_API_KEY
    global LANGUAGE
    global LANGUAGE2
    global base_url
    
    # regex to search trailer depending on the language
    languages = [(LANGUAGE,r"bande[-\s]?annonce"), (LANGUAGE2,r"trailer")]
    trailer_links = []
    vidt = f"{media_type}/{tmdbid}"
    # search for the corresponding trailer depending on the language
    for language, pattern in languages:
        if vidt:
            youtube_key = search_trailer_key(vidt, language, pattern)
            if youtube_key:
                trailer_links.append(f"https://youtu.be/{youtube_key}")

    if trailer_links:
        if len(trailer_links) == 2:
            return f"• Trailer FR: {trailer_links[0]}\n • Trailer EN: {trailer_links[1]}"
        elif len(trailer_links) == 1:
            return f"• Trailer: {trailer_links[0]}\n"

# function to search for the trailer key in the tmdb API
def search_trailer_key(vidt, language, pattern):
    # parameters
    global TMDB_API_KEY
    global base_url

    regex = re.compile(r"^[a-z]+/[0-9]+")
    if "season" in vidt:
        vidt = regex.findall(vidt)[0]

    # search for the corresponding trailer depending on the language
    url = f"{base_url}/{vidt}/videos"
    params = {
        'api_key': TMDB_API_KEY,
        'language': language,
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])

            for video in results:
                if re.search(pattern, video.get("name", ""), flags=re.IGNORECASE):
                    return video.get("key")

    except requests.exceptions.RequestException as e:
        print(f"search_trailer_key request error: {e}")

    return None # trailer key not found

def is_season_or_series(data):
    # Check if it's a season or a series
    return data.get('media_type', '') == "tv" and data.get('season_number', '') != ""

@app.route('/api/jellyseerr', methods=['POST'])
def receive_data():
  if not request.is_json:
    return jsonify({'message': 'Data is not json!'}), 400

  data = request.json
  media_type = data.get('media_type', '')
  tmdbid = data.get('tmdbid', '')
  tvdbid = data.get('tvdbid', '')
  requestedBy_username = data.get('requestedBy_username', '')

  if is_season_or_series(data):
    # It's a season
    season_number = data.get('season_number', '')
    serie_name = data.get('serie_name', '')
    tmdb_details = get_tmdb_details('tv', tmdbid, language=LANGUAGE)
    title = tmdb_details.get('name', '')
    poster_id = tmdb_details.get('poster_path', '')
    poster_path = download_and_get_poster_by_id(poster_id)
    overview = tmdb_details.get('overview', '')
    media_link = f"● TVDb: https://thetvdb.com/series/{serie_name}/seasons/official/{season_number}"
    trailer = get_trailer_link('tv', tmdbid)
    fmessage = format_message(title, requestedBy_username, overview, media_link, trailer)
    send_whatsapp(WHATSAPP_NUMBER, fmessage, True, poster_path)
  elif media_type == "movie":
    # It's a movie
    tmdb_details = get_tmdb_details(media_type, tmdbid, language=LANGUAGE)
    title = tmdb_details.get('title', '')
    overview = tmdb_details.get('overview', '')
    poster_id = tmdb_details.get('poster_path', '')
    poster_path = download_and_get_poster_by_id(poster_id)
    trailer = get_trailer_link(media_type, tmdbid)
    media_link = f"● TMDb: https://tmdb.org/{media_type}/{tmdbid}"
    fmessage = format_message(title, requestedBy_username, overview, media_link, trailer)
    send_whatsapp(WHATSAPP_NUMBER, fmessage, True, poster_path)
  else:
    # It's an episode
    tmdb_details = get_tmdb_details(media_type, tmdbid, language=LANGUAGE2)
    title = tmdb_details.get('title', '')
    overview = tmdb_details.get('overview', '')
    media_link = f"● TMDb: https://tmdb.org/{media_type}/{tmdbid}"
    fmessage = format_message(title, requestedBy_username, overview, media_link)
    send_whatsapp(WHATSAPP_NUMBER, fmessage, False, None)

  if poster_path:
    os.remove(poster_path)

  return jsonify({'message': 'Data received successfully!'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=7778)
