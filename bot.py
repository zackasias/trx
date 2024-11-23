import os
import re
import shutil
import subprocess
from urllib.parse import urlparse
from telethon import TelegramClient, events
from mutagen.easyid3 import EasyID3
from mutagen import File

# Set up your MTProto API credentials (API ID and hash from Telegram's Developer Portal)
api_id = '10074048'
api_hash = 'a08b1ed3365fa3b04bcf2bcbf71aff4d'
session_name = 'beatport_downloader'

# Regular expressions for Beatport and Crates.co URLs
beatport_pattern = r'^https:\/\/www\.beatport\.com\/track\/[\w -]+\/\d+$'
crates_pattern = r'^https:\/\/crates\.co\/track\/[\w -]+\/\d+$'

# Initialize the client
client = TelegramClient(session_name, api_id, api_hash)

# Function to extract and update metadata
def extract_and_update_metadata(filepath):
    """
    Extract and update metadata to include featured artists in albumartist.
    """
    # Load the audio file's metadata
    audio = EasyID3(filepath)
    
    # Extract artist and album artist
    artist = audio.get('artist', ['Unknown Artist'])[0]
    album_artist = audio.get('albumartist', [artist])[0]  # Default to artist if albumartist is missing

    # Check for featured artists in the 'artist' field
    # Look for keywords like 'feat.', 'ft.', etc.
    featured_match = re.search(r'(feat\.|ft\.)\s*(.+)', artist, re.IGNORECASE)
    if featured_match:
        featured_artists = featured_match.group(2)
        # Append featured artists to album artist
        album_artist = f"{album_artist} (feat. {featured_artists})"

    # Update metadata
    audio['albumartist'] = album_artist
    audio.save()

    return artist, album_artist

# Start the client and listen for new messages
@client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await event.reply("Hi! I'm Beatport Track Downloader using MTProto API.\n\n"
                      "Commands:\n"
                      "/download <track_url> - Download a track from Beatport or Crates.co.\n\n"
                      "Example:\n"
                      "/download https://www.beatport.com/track/take-me/17038421\n"
                      "/download https://crates.co/track/take-me/17038421")

@client.on(events.NewMessage(pattern='/download'))
async def download_handler(event):
    try:
        input_text = event.message.text.split(maxsplit=1)[1]
        
        # Validate the track URL against Beatport and Crates.co patterns
        is_beatport = re.match(rf'{beatport_pattern}', input_text)
        is_crates = re.match(rf'{crates_pattern}', input_text)

        if not (is_beatport or is_crates):
            await event.reply('Invalid track link. Please provide a valid Beatport or Crates.co URL.')
            return

        # Convert Crates.co link to Beatport link if necessary
        if is_crates:
            input_text = input_text.replace('crates.co', 'www.beatport.com')

        await event.reply("Downloading and processing the audio file... Please wait.")
        url = urlparse(input_text)
        components = url.path.split('/')

        # Run the orpheus script to download the track
        track_id = components[-1]
        download_dir = f'downloads/{track_id}'
        os.makedirs(download_dir, exist_ok=True)
        subprocess.run(['python', 'orpheus.py', input_text], check=True)

        # Get the downloaded filename
        downloaded_files = os.listdir(download_dir)
        if not downloaded_files:
            raise FileNotFoundError("No file downloaded. Check the orpheus.py script.")

        filepath = os.path.join(download_dir, downloaded_files[0])

        # Extract and update metadata
        artist, album_artist = extract_and_update_metadata(filepath)
        audio = File(filepath, easy=True)
        title = audio.get('title', ['Unknown Title'])[0]

        # Create the new filename based on artist and title
        new_filename = f"{album_artist} - {title}.flac"
        new_filepath = os.path.join(download_dir, new_filename)

        # Convert the downloaded file to FLAC format using ffmpeg
        subprocess.run(['ffmpeg', '-i', filepath, new_filepath], check=True)

        # Send the renamed FLAC file to the user
        await client.send_file(event.chat_id, new_filepath)

    except Exception as e:
        await event.reply(f"An error occurred: {str(e)}")

    finally:
        # Clean up the downloaded files
        if os.path.exists(download_dir):
            shutil.rmtree(download_dir)

async def main():
    # Start the Telegram client
    async with client:
        print("Client is running...")
        await client.run_until_disconnected()

if __name__ == '__main__':
    client.loop.run_until_complete(main())
