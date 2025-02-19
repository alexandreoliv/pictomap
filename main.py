import os
import glob
import exifread
from PIL import Image
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from datetime import datetime
import time
from googletrans import Translator
import unicodedata


def get_exif_data(image_path):
    """Extract EXIF data from an image."""
    with open(image_path, 'rb') as f:
        tags = exifread.process_file(f)
    return tags

def get_gps_coordinates(tags):
    """Extract GPS coordinates from EXIF tags."""
    try:
        gps_latitude = tags['GPS GPSLatitude'].values
        gps_latitude_ref = tags['GPS GPSLatitudeRef'].values[0]
        gps_longitude = tags['GPS GPSLongitude'].values
        gps_longitude_ref = tags['GPS GPSLongitudeRef'].values[0]

        lat = convert_to_degrees(gps_latitude)
        lon = convert_to_degrees(gps_longitude)
        
        if gps_latitude_ref != 'N':
            lat = -lat
        if gps_longitude_ref != 'E':
            lon = -lon
        
        return lat, lon
    except KeyError:
        return None

def convert_to_degrees(value):
    """Convert GPS coordinates from EXIF format to degrees."""
    d, m, s = value
    return d.num / d.den + (m.num / m.den) / 60 + (s.num / s.den) / 3600

def get_location(lat, lon, retries=3, delay=2):
    """Get city and country from GPS coordinates with retry logic."""
    geolocator = Nominatim(user_agent="photo_exif_locator", timeout=10)
    
    for attempt in range(retries):
        try:
            location = geolocator.reverse((lat, lon), exactly_one=True)
            return location.raw['address'] if location else None
        except GeocoderTimedOut:
            print(f"Geocoder timed out. Retrying {attempt + 1}/{retries}...")
            time.sleep(delay)
    
    print("Geocoder failed after multiple attempts.")
    return None

def get_date_taken(tags):
    """Extract date taken from EXIF tags."""
    try:
        date_str = tags['EXIF DateTimeOriginal'].values
        return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
    except KeyError:
        return None

def is_non_latin(text):
    """Check if the text contains non-Latin characters."""
    for char in text:
        if 'LATIN' not in unicodedata.name(char):
            return True
    return False

def scan_images(directory):
    """Scan for images recursively and extract metadata."""
    print("Scanning for images...\n")

    image_paths = glob.glob(os.path.join(directory, '**', '*.jpg'), recursive=True) + \
                  glob.glob(os.path.join(directory, '**', '*.jpeg'), recursive=True)
    
    results = {}
    current_folder = None
    folder_image_count = 0
    folder_index = 0  # Initialize folder-specific index
    for image_path in image_paths:
        folder_name = os.path.basename(os.path.dirname(image_path))
        
        # Reset index and count for each new folder
        if folder_name != current_folder:
            current_folder = folder_name
            folder_image_count = sum(1 for path in image_paths if os.path.basename(os.path.dirname(path)) == folder_name)
            folder_index = 0  # Reset folder-specific index
        
        folder_index += 1  # Increment folder-specific index
        # Update progress for the current folder
        print(f"Processing image {folder_index} out of {folder_image_count} in folder: {folder_name}", end='\r')
        
        tags = get_exif_data(image_path)
        gps = get_gps_coordinates(tags)
        date_taken = get_date_taken(tags)
        
        location_info = None
        if gps:
            location_info = get_location(*gps)
        
        # Only consider images with either city or country
        if location_info and (location_info.get('city') or location_info.get('country')):
            filename = os.path.basename(image_path)
            date_str = date_taken.strftime('%Y-%m-%d') if date_taken else 'Unknown'
            city = location_info.get('city', 'Unknown')
            country = location_info.get('country', 'Unknown')
            
            # Initialize folder in results if not present
            if folder_name not in results:
                results[folder_name] = []
            
            # Check if the city has already appeared on the same day
            existing_entry = next((entry for entry in results[folder_name] if entry['date'] == date_str and entry['city'] == city), None)
            if existing_entry:
                # Replace if the new image is earlier
                if date_taken < datetime.strptime(existing_entry['date'], '%Y-%m-%d'):
                    existing_entry.update({
                        'filename': filename,
                        'date': date_str,
                        'city': city,
                        'country': country
                    })
            else:
                results[folder_name].append({
                    'filename': filename,
                    'date': date_str,
                    'city': city,
                    'country': country
                })
    
    # Sort images in each folder by date
    for folder in results:
        results[folder].sort(key=lambda x: x['date'])
    
    # Translate city and country to English if they contain non-Latin characters
    translator = Translator()  # Initialize the translator
    translation_count = 0  # Initialize translation counter
    for folder in results:
        for entry in results[folder]:
            if is_non_latin(entry['city']):
                entry['city'] = translator.translate(entry['city'], dest='en').text
                translation_count += 1  # Increment translation counter
            if is_non_latin(entry['country']):
                entry['country'] = translator.translate(entry['country'], dest='en').text
                translation_count += 1  # Increment translation counter
    
    print("\nImage scanning complete.")
    print(f"Total translations performed: {translation_count}\n")
    return results

if __name__ == "__main__":
    directory = "/home/alex/Downloads/photos/doha"
    print(f"Starting scan in directory: {directory}")
    image_data = scan_images(directory)
    for folder, images in image_data.items():
        print(f"Folder: {folder}")
        for data in images:
            print(f"  Filename: {data['filename']}, Date: {data['date']}, City: {data['city']}, Country: {data['country']}")
    print("\nProcessing complete.")
