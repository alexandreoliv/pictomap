import os
import glob
import exifread
from PIL import Image
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from datetime import datetime
import time
import sys
import contextlib
import json


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
            location = geolocator.reverse((lat, lon), exactly_one=True, language='en')
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

@contextlib.contextmanager
def suppress_stderr():
    """Context manager to suppress standard error output."""
    with open(os.devnull, 'w') as devnull:
        old_stderr = sys.stderr
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stderr = old_stderr

def round_coordinates(lat, lon, precision=1):
    """Round GPS coordinates to reduce redundant Geopy calls."""
    return round(lat, precision), round(lon, precision)

def scan_images(directory, precision=1):
    """Scan for images recursively and extract metadata."""
    print("Scanning for images...\n")

    image_paths = glob.glob(os.path.join(directory, '**', '*.jpg'), recursive=True) + \
                  glob.glob(os.path.join(directory, '**', '*.jpeg'), recursive=True)
    
    results = {}
    current_folder = None
    folder_image_count = 0
    folder_index = 0  # Initialize folder-specific index
    total_files = len(image_paths)  # Get total number of images
    processed_files = 0  # Initialize processed files counter
    start_time = time.time()  # Start the timer

    # Initialize counters
    geopy_count = 0
    geopy_problem_count = 0
    exif_count = 0
    valid_exif_count = 0
    exif_problem_count = 0

    # Initialize location cache
    location_cache = {}

    # Define precision accuracy mapping
    precision_accuracy = {
        0: "~111 km", # Country-level grouping
        1: "~11.1 km", # City-level grouping
        2: "~1.11 km", # Large neighborhood grouping
        3: "~111 m", # Small neighborhood grouping
        4: "~11.1 m", # Street-level grouping
        5: "~1.11 m", # Individual building grouping
        6: "~0.11 m", # Precise GPS location, close to consumer GPS accuracy
        7: "Less than 1 cm" # Extremely fine precision, mostly unnecessary
    }

    for image_path in image_paths:
        folder_name = os.path.basename(os.path.dirname(image_path))

        # Reset index and count for each new folder
        if folder_name != current_folder:
            current_folder = folder_name
            folder_image_count = sum(1 for path in image_paths if os.path.basename(os.path.dirname(path)) == folder_name)
            folder_index = 0  # Reset folder-specific index

        folder_index += 1  # Increment folder-specific index
        processed_files += 1  # Increment processed files

        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        hours = int(elapsed_time // 3600)
        minutes = int((elapsed_time % 3600) // 60)
        seconds = int(elapsed_time % 60)

        elapsed_str = f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

        # Calculate progress percentage
        progress_percentage = (processed_files / total_files) * 100

        # Create a visually appealing progress message
        progress_message = (
            f"\033[1;34m⏳ Time elapsed:\033[0m {elapsed_str}  |  "  # Bold blue time
            f"\033[1;35m🌍 Precision:\033[0m {precision} ({precision_accuracy.get(precision, 'Unknown')})  |  "  # Bold magenta precision
            f"\033[1;32m✅ Processed:\033[0m {processed_files}/{total_files} ({progress_percentage:.2f}%)  |  "  # Bold green processed count
            f"\033[1;36m📂 Folder:\033[0m {folder_name}  |  "  # Bold cyan folder
            f"\033[1;33m📷 Image:\033[0m {folder_index}/{folder_image_count}"  # Bold yellow image count
        )

        # Print single-line updating message (overwrite previous)
        print('\r' + ' ' * 180, end='\r')  # Clear previous output
        print(progress_message, end='\r', flush=True)  # Overwrite previous line
        
        # Process the image
        try:
            with suppress_stderr():
                tags = get_exif_data(image_path)
            exif_count += 1
            gps = get_gps_coordinates(tags)
            date_taken = get_date_taken(tags)
            if gps or date_taken:
                valid_exif_count += 1
        except Exception as e:
            exif_problem_count += 1
            continue
        
        location_info = None
        if gps:
            try:
                rounded_gps = round_coordinates(*gps, precision=precision)  # Round the GPS coordinates
                if rounded_gps in location_cache:
                    location_info = location_cache[rounded_gps]  # Use cached location
                else:
                    location_info = get_location(*gps)
                    if location_info:
                        location_cache[rounded_gps] = location_info  # Store in cache
                    geopy_count += 1  # Increment geopy count
            except Exception as e:
                geopy_problem_count += 1
                continue
        
        # Only consider images with either city or country
        if location_info and (location_info.get('city') or location_info.get('country')):
            filename = os.path.basename(image_path)
            date_str = date_taken.strftime('%Y-%m-%d') if date_taken else 'Unknown'
            time_str = date_taken.strftime('%H:%M:%S') if date_taken else 'Unknown'
            city = location_info.get('city', 'Unknown')
            country = location_info.get('country', 'Unknown')
            
            # Initialize folder in results if not present
            if folder_name not in results:
                results[folder_name] = []
            
            # Check if the city has already appeared on the same day
            existing_entry = next((entry for entry in results[folder_name] if entry['date'] == date_str and entry['city'] == city), None)
            if existing_entry:
                # Replace if the new image is earlier and both dates are valid
                if date_taken and existing_entry['date'] != 'Unknown':
                    if date_taken < datetime.strptime(existing_entry['date'] + ' ' + existing_entry.get('time', '00:00:00'), '%Y-%m-%d %H:%M:%S'):
                        existing_entry.update({
                            'filename': filename,
                            'date': date_str,
                            'time': time_str,
                            'city': city,
                            'country': country,
                            'coordinates': gps
                        })
            else:
                results[folder_name].append({
                    'filename': filename,
                    'date': date_str,
                    'time': time_str,
                    'city': city,
                    'country': country,
                    'coordinates': gps
                })
    
    # Sort images in each folder by date and time
    for folder in results:
        results[folder].sort(key=lambda x: (x['date'], x['time']))
    
    # Prepare summary data
    summary = {
        "total_running_time": elapsed_str,
        "total_geopy_calls": geopy_count,
        "total_geopy_problems": geopy_problem_count,
        "original_number_of_files": total_files,
        "number_of_jpg_and_jpeg_files": total_files,
        "number_of_jpg_and_jpeg_files_with_exif": exif_count,
        "number_of_jpg_and_jpeg_files_with_valid_exif": valid_exif_count,
        "number_of_exifs_with_problems": exif_problem_count
    }
    
    # Combine summary and results
    output_data = {
        "summary": summary,
        "results": results
    }
    
    print("\nImage scanning complete.")
    
    # Save results as JSON to a file
    json_filename = 'image_metadata.json'
    with open(json_filename, 'w') as json_file:
        json.dump(output_data, json_file, indent=4)
    
    print(f"JSON file '{json_filename}' created successfully.\n")

    print(f"Total running time: {elapsed_str}")
    print(f"Total Geopy calls made: {geopy_count}")
    print(f"Total Geopy problems encountered: {geopy_problem_count}")
    print(f"Original number of files: {total_files}")
    print(f"Number of .jpg and .jpeg files: {total_files}")
    print(f"Number of .jpg and .jpeg files with EXIF: {exif_count}")
    print(f"Number of .jpg and .jpeg files with valid EXIF: {valid_exif_count}")
    print(f"Number of EXIFs with problems: {exif_problem_count}\n")
    
    return results

if __name__ == "__main__":
    directory = "/home/alex/Downloads/photos/doha"
    print(f"Starting scan in directory: {directory}")
    image_data = scan_images(directory)
    for folder, images in image_data.items():
        print(f"Folder: {folder}")
        for data in images:
            print(f"  Filename: {data['filename']}, Date: {data['date']}, Time: {data['time']}, City: {data['city']}, Country: {data['country']}, Coordinates: {data['coordinates']}")
    print("\nProcessing complete.")
