import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import logging
from math import ceil

import smtplib
from email.message import EmailMessage
import datetime # To add timestamp to email subject


# --- Configuration ---
# Make sure SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, and SPOTIPY_REDIRECT_URI
# are set as environment variables.

# !! Replace with the ID of the playlist you want to sync TO !!
TARGET_PLAYLIST_ID = '1EFdxSWFTyTHRx6DQsTj7b'

# !! Replace with your Spotify Username if needed for scope, otherwise leave None !!
# Usually not strictly required if using SpotifyOAuth correctly, but good to have if issues arise.
USERNAME = 'eaar6a6x5vphvycqt28u65yhw'

# Permissions needed: Read Liked Songs, Modify target playlist (public/private)
SCOPE = 'user-library-read playlist-modify-public playlist-modify-private'

# Max items per API call for adding/removing tracks
API_LIMIT = 100

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(), logging.FileHandler("spotify_liked_sync.log")])

# --- Helper Functions ---

def get_all_items(spotify_call):
    """
    Generic function to retrieve all items from a paginated Spotify API endpoint.

    Args:
        spotify_call: A function that returns a page of results
                      (e.g., sp.current_user_saved_tracks or sp.playlist_items).

    Returns:
        A list of all items retrieved.
    """
    all_items = []
    try:
        # Request fewer items initially if memory/performance becomes an issue,
        # but 50 is the max allowed for most endpoints like saved_tracks.
        results = spotify_call(limit=50)
        if results:
            all_items.extend(results['items'])
            while results['next']:
                # Use sp.next to handle pagination easily
                results = sp.next(results)
                if results and results['items']:
                    all_items.extend(results['items'])
        else:
             logging.warning(f"Initial call to {getattr(spotify_call, '__name__', 'spotify_call')} returned no results.")
    except Exception as e:
        logging.error(f"Error fetching items with {getattr(spotify_call, '__name__', 'spotify_call')}: {e}")
        # Optionally re-raise or handle more gracefully depending on needs
        # raise e
    return all_items

def get_track_details(track_object):
    """Extracts URI, name, and artist string from a track object."""
    if not track_object or 'uri' not in track_object or 'name' not in track_object:
        return None, None # Return None if essential parts are missing

    uri = track_object['uri']
    name = track_object['name']
    
    # Handle potential missing artists list or malformed artist objects
    try:
        artists = ", ".join([artist['name'] for artist in track_object.get('artists', []) if artist and 'name' in artist])
    except Exception:
        artists = "Unknown Artist" # Fallback artist name
        
    return uri, {'name': name, 'artists': artists}

def get_liked_track_details(sp):
    """Gets details (URI, name, artists) for all 'Liked Songs'."""
    logging.info("Fetching liked songs details...")
    # current_user_saved_tracks already includes the full track object
    saved_tracks_items = get_all_items(sp.current_user_saved_tracks)
    
    liked_details = {}
    skipped_count = 0
    for item in saved_tracks_items:
        if item and 'track' in item:
            uri, details = get_track_details(item['track'])
            if uri and details:
                liked_details[uri] = details
            else:
                 skipped_count += 1
                 logging.warning(f"Skipping invalid liked track item: {item.get('track', {}).get('uri', 'URI Missing')}")
        else:
            skipped_count += 1
            logging.warning(f"Skipping invalid saved_tracks item structure: {item}")

    if skipped_count > 0:
        logging.warning(f"Skipped {skipped_count} liked tracks due to missing data.")
    logging.info(f"Found details for {len(liked_details)} liked songs.")
    return liked_details

def get_playlist_track_details(sp, playlist_id):
    """Gets details (URI, name, artists) for all tracks in a playlist."""
    logging.info(f"Fetching track details from playlist ID: {playlist_id}...")
    # Specify fields needed to ensure name and artists are included
    fields = 'items(track(uri,name,artists(name))),next'
    playlist_items = get_all_items(lambda limit=50, offset=0: sp.playlist_items(playlist_id, limit=limit, offset=offset, fields=fields))

    playlist_details = {}
    skipped_count = 0
    for item in playlist_items:
        if item and 'track' in item and item['track']: # Ensure track object exists
            uri, details = get_track_details(item['track'])
            if uri and details:
                 playlist_details[uri] = details
            else:
                # Log if track object exists but details extraction fails
                skipped_count += 1
                logging.warning(f"Skipping invalid playlist track item: {item.get('track', {}).get('uri', 'URI Missing')}")
        elif item and item.get('track') is None:
            # Log specifically if the item exists but has no track (e.g., local file, podcast episode if not filtered)
            skipped_count += 1
            logging.debug(f"Skipping non-track item in playlist: {item}") # Use debug as this might be expected
        else:
             # Log other unexpected item structures
             skipped_count += 1
             logging.warning(f"Skipping invalid playlist item structure: {item}")

    if skipped_count > 0:
         logging.warning(f"Skipped {skipped_count} items in playlist {playlist_id} (may include non-tracks or tracks with missing data).")
    logging.info(f"Found details for {len(playlist_details)} tracks in playlist {playlist_id}.")
    return playlist_details


def add_tracks_to_playlist(sp, playlist_id, track_uris_to_add, track_details_lookup):
    """Adds tracks to the specified playlist, logging names and artists."""
    if not track_uris_to_add:
        logging.info("No new tracks to add.")
        return

    uris_list = list(track_uris_to_add)
    num_chunks = ceil(len(uris_list) / API_LIMIT)
    logging.info(f"Adding {len(uris_list)} tracks in {num_chunks} chunk(s)...")

    for i in range(num_chunks):
        start_index = i * API_LIMIT
        end_index = start_index + API_LIMIT
        chunk = uris_list[start_index:end_index]
        try:
            sp.playlist_add_items(playlist_id, chunk)
            logging.info(f"Added chunk {i+1}/{num_chunks} ({len(chunk)} tracks) to playlist {playlist_id}.")
            # Log individual tracks added in this chunk with details
            for uri in chunk:
                details = track_details_lookup.get(uri, {'name': 'N/A', 'artists': 'N/A'})
                logging.info(f"  ADDED: {details['name']} by {details['artists']} ({uri})")
        except Exception as e:
            logging.error(f"Error adding chunk {i+1} to playlist {playlist_id}: {e}")
            # Log failed URIs for debugging
            failed_details_log = []
            for uri in chunk:
                 details = track_details_lookup.get(uri, {'name': 'N/A', 'artists': 'N/A'})
                 failed_details_log.append(f"{details['name']} by {details['artists']} ({uri})")
            logging.error(f"  Failed chunk details:\n  " + "\n  ".join(failed_details_log))


def remove_tracks_from_playlist(sp, playlist_id, track_uris_to_remove, track_details_lookup):
    """Removes tracks from the specified playlist, logging names and artists."""
    if not track_uris_to_remove:
        logging.info("No tracks to remove.")
        return

    uris_list = list(track_uris_to_remove)
    num_chunks = ceil(len(uris_list) / API_LIMIT)
    logging.info(f"Removing {len(uris_list)} tracks in {num_chunks} chunk(s)...")

    for i in range(num_chunks):
        start_index = i * API_LIMIT
        end_index = start_index + API_LIMIT
        chunk = uris_list[start_index:end_index]
        try:
            # Spotipy's remove function expects a list of URIs
            sp.playlist_remove_all_occurrences_of_items(playlist_id, chunk)
            logging.info(f"Removed chunk {i+1}/{num_chunks} ({len(chunk)} tracks) from playlist {playlist_id}.")
            # Log individual tracks removed in this chunk with details
            for uri in chunk:
                details = track_details_lookup.get(uri, {'name': 'N/A', 'artists': 'N/A'})
                logging.info(f"  REMOVED: {details['name']} by {details['artists']} ({uri})")
        except Exception as e:
            logging.error(f"Error removing chunk {i+1} from playlist {playlist_id}: {e}")
            # Log failed URIs for debugging
            failed_details_log = []
            for uri in chunk:
                 details = track_details_lookup.get(uri, {'name': 'N/A', 'artists': 'N/A'})
                 failed_details_log.append(f"{details['name']} by {details['artists']} ({uri})")
            logging.error(f"  Failed chunk details:\n  " + "\n  ".join(failed_details_log))

            
def format_email_body(added_uris, removed_uris, details_lookup):
    """Formats the email body with lists of added and removed tracks."""
    body = "Spotify Liked Songs Sync Results:\n\n"

    if added_uris:
        body += f"--- Added Tracks ({len(added_uris)}) ---\n"
        for uri in added_uris:
            details = details_lookup.get(uri, {'name': 'N/A', 'artists': 'N/A'})
            body += f"- {details['name']} by {details['artists']}\n" # ({uri})\n" # Optionally include URI
        body += "\n"
    else:
        body += "--- No Tracks Added ---\n\n"

    if removed_uris:
        body += f"--- Removed Tracks ({len(removed_uris)}) ---\n"
        for uri in removed_uris:
            details = details_lookup.get(uri, {'name': 'N/A', 'artists': 'N/A'})
            body += f"- {details['name']} by {details['artists']}\n" # ({uri})\n" # Optionally include URI
        body += "\n"
    else:
        body += "--- No Tracks Removed ---\n\n"

    return body

def send_gmail(subject, body, sender, password, recipient):
    """Sends an email using Gmail SMTP."""
    if not all([sender, password, recipient]):
        logging.warning("Email configuration incomplete. Skipping email notification.")
        return

    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient

    try:
        logging.info(f"Attempting to send email notification to {recipient}...")
        # Connect to Gmail SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Secure the connection
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        logging.info("Email notification sent successfully.")
    except smtplib.SMTPAuthenticationError:
        logging.error("Email SMTP Authentication Error. Check sender email/App Password.")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")            

        
# --- Main Execution ---
if __name__ == "__main__":
    logging.info("Starting Spotify Liked Songs Sync...")

    if TARGET_PLAYLIST_ID == 'YOUR_TARGET_PLAYLIST_ID':
        logging.error("Please update the TARGET_PLAYLIST_ID variable in the script.")
        exit()

    # --- Retrieve Email Config ---
    sender_email = os.environ.get('GMAIL_SENDER_EMAIL')
    sender_password = os.environ.get('GMAIL_SENDER_APP_PASSWORD')
    recipient_email = os.environ.get('GMAIL_RECIPIENT_EMAIL')
    email_configured = all([sender_email, sender_password, recipient_email])
    if not email_configured:
         logging.warning("Email environment variables (GMAIL_SENDER_EMAIL, GMAIL_SENDER_APP_PASSWORD, GMAIL_RECIPIENT_EMAIL) not fully set. Email notifications will be disabled.")

    try:
        # Authenticate
        auth_manager = SpotifyOAuth(
            scope=SCOPE,
            username=USERNAME,
            open_browser=False # Set to False for non-interactive/scheduled runs
        )
        sp = spotipy.Spotify(auth_manager=auth_manager)
        logging.info("Authentication successful.")

        # Get current state with details
        liked_details = get_liked_track_details(sp)
        playlist_details = get_playlist_track_details(sp, TARGET_PLAYLIST_ID)

        # Create sets of URIs for comparison
        liked_uris = set(liked_details.keys())
        playlist_uris = set(playlist_details.keys())

        # Calculate differences
        tracks_to_add_uris = liked_uris - playlist_uris
        tracks_to_remove_uris = playlist_uris - liked_uris

        # Create a combined lookup for logging track details
        all_track_details = {**playlist_details, **liked_details}

        logging.info(f"Tracks to add: {len(tracks_to_add_uris)}")
        logging.info(f"Tracks to remove: {len(tracks_to_remove_uris)}")

        # --- Perform updates ---
        # Check if there are actual changes before calling API modify functions
        if tracks_to_add_uris:
            add_tracks_to_playlist(sp, TARGET_PLAYLIST_ID, tracks_to_add_uris, all_track_details)
        else:
             logging.info("No tracks to add.")

        if tracks_to_remove_uris:
             remove_tracks_from_playlist(sp, TARGET_PLAYLIST_ID, tracks_to_remove_uris, all_track_details)
        else:
             logging.info("No tracks to remove.")
        # --- End Perform updates ---


        # --- Send Email Notification (if configured) ---
        if email_configured:
            # Prepare email content regardless of changes
            email_subject = f"Spotify Sync Status - {datetime.date.today()}" # Changed subject slightly
            email_body = format_email_body(tracks_to_add_uris, tracks_to_remove_uris, all_track_details)

            # Add a top line indicating status explicitly
            if not tracks_to_add_uris and not tracks_to_remove_uris:
                 email_body = "Spotify Sync Ran: No changes detected.\n\n" + email_body
                 logging.info("No changes detected. Preparing confirmation email.")
            else:
                 email_body = "Spotify Sync Ran: Changes detected.\n\n" + email_body
                 logging.info("Changes detected, preparing results email.")

            # Send the email
            send_gmail(email_subject, email_body, sender_email, sender_password, recipient_email)
        # --- End Send Email Notification ---

        logging.info("Sync process completed.")

    except spotipy.SpotifyException as e:
         logging.error(f"Spotify API error: {e}")
         if e.http_status == 401 or e.http_status == 403:
              logging.error("Authentication error. Check credentials, scope, or try re-authenticating interactively to refresh the cache.")
         exit(1)
    except Exception as e:
        logging.exception(f"An unexpected error occurred during the sync process: {e}")
        exit(1)        