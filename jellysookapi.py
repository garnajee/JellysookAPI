#!/usr/bin/env python3

from flask import Flask, request, jsonify
import requests
import tempfile
import io
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
    message += f"```overview```\n"
  
  message += f"{media_link}\n"
  
  if trailer:
    message += trailer

  return message

def get_poster(image_url):
  # get temporary poster path
  with tempfile.NamedTemporaryFile() as temp:
    response = requests.get(image_url)
    temp.write(response.content)
  return temp.name

def is_episode_added(title):
    # Check if the title matches the format "Episode added • ...  SXYZEXYZ ... - Épisode XYZ..."
    match = re.search(r'(Episode added • .+?) - Épisode \d+', title)

    if match:
        new_title = match.group(1)
        return True, new_title
    else:
        return False, title

# function to get the synopsis of the video from tmdb API
def get_synopsis(vidt):
    # parameters
    global TMDB_API_KEY
    global LANGUAGE
    global LANGUAGE2
    global base_url

    languages = [LANGUAGE, LANGUAGE2]

    for language in languages:
        if vidt:
            url = f"{base_url}/{vidt}?api_key={TMDB_API_KEY}&language={language}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()["overview"]

    return None # synopsis not found

# function to get the shortened youtube trailer link from tmdb API
def get_trailer_link(vidt):
    # parameters
    global TMDB_API_KEY
    global LANGUAGE
    global LANGUAGE2
    global base_url
    
    # regex to search trailer depending on the language
    languages = [(LANGUAGE,r"bande[-\s]?annonce"), (LANGUAGE2,r"trailer")]
    trailer_links = []
    
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

# function to get the poster url from tmdb API
def get_tmdb_poster_url(vidt):
    global TMDB_API_KEY
    global base_url
    global LANGUAGE

    regex = re.compile(r"^[a-z]+/[0-9]+")
    if "season" in vidt:
        vidt = regex.findall(vidt)[0]

    # poster api url
    tmdb_url = f"{base_url}/{vidt}/images?api_key={TMDB_API_KEY}&language={LANGUAGE[:-3]}"

    try:
        # request to the TMDB API
        response = requests.get(tmdb_url, timeout=10)
        # check if the request was successful
        response.raise_for_status()
        # parse the response JSON
        results = response.json()

        # get the first poster url
        if 'posters' in results and len(results['posters']) > 0:
            poster_url = results['posters'][0]['file_path']
            full_poster_url = f"https://image.tmdb.org/t/p/w342{poster_url}"
            return full_poster_url

        # try with other language
        tmdb_url2 = f"{base_url}/{vidt}/images?api_key={TMDB_API_KEY}"
        response = requests.get(tmdb_url2, timeout=10)
        response.raise_for_status()
        results = response.json()
        if 'posters' in results and len(results['posters']) > 0:
            poster_url = results['posters'][0]['file_path']
            full_poster_url = f"https://image.tmdb.org/t/p/w342{poster_url}"
            return full_poster_url
        else:
            return jsonify({'message': 'No poster found'}), 400

    except requests.exceptions.RequestException as req_err:
        return jsonify({'message': f'get poster: Request error: {str(req_err)}'}), 400
    except requests.exceptions.HTTPError as http_err:
        return jsonify({'message': f'get poster: HTTP error: {str(http_err)}'}), 400
    except KeyError as key_err:
        return jsonify({'message': f'get poster: Key not found: {str(key_err)}'}), 400
    except IndexError as index_err:
        return jsonify({'message': f'get poster: Index out of bounds: {str(index_err)}'}), 400
    except Exception as e:
        return jsonify({'message': f'get poster: Another error occurred: {str(e)}'}), 400

# function to shorten links
def shorten_link(link):
    # find domain name in the link
    domain = link.split("//")[1].split("/")[0]

    if domain == "www.themoviedb.org":
        # replace useless part of the link for TMDb
        return link.replace("https://www.themoviedb.org/", "https://tmdb.org/")
    elif domain == "www.imdb.com":
        # replace useless part of the link for IMDb
        return link.replace("https://www.imdb.com/", "https://imdb.com/")
    else:
        # return the link if domain name not recognize
        return link

@app.route('/api/jellyseerr', methods=['POST'])
def receive_data():
  if not request.is_json:
    return jsonify({'message': 'Data is not json!'}), 400

  data = request.json
  title = data.get('title', '')
  overview = data.get('overview', '')
  media_type = data.get('media_type', '')
  tmdbid = data.get('tmdbid', '')
  tvdbid = data.get('tvdbid', '')
  requestedBy_username = data.get('requestedBy_username', '')
  media_status = data.get('media_status', '')
  image_url = data.get('image_url', '')

  if media_type == "movie":
    # format tmdb_link
    media_link = f"● TMDb: https://tmdb.org/{media_type}/{tmdbid}"
    # download and get poster path
    if image_url:
      poster_path = get_poster(image_url)
    else:
      poster_url = get_tmdb_poster_url(media_type, tmdbid)
      poster_path = get_poster(poster_url)
    # get trailer link
    trailer = get_trailer(media_type, tmdbid)
    # format message
    fmessage = format_message(title, overview, media_link, trailer)
    # send message
    send_whatsapp(phone, fmessage, True, poster_path)
  else:
    # if it's a season
      pass
    # if it's an episode
      # no poster
      # no trailer
      # overview only if exists
      media_link = "● TVDb: https://thetvdb.com/series/{serie_name}/seasons/official/{season_number}"
      fmessage = format_message(title, requestedBy_username, overview, media_link)
      send_whatsapp(phone, fmessage, False, None)

    return jsonify({'message': 'Data received successfully!'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=7778)
