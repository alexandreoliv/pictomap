import os
import glob
import exifread
from datetime import datetime
import time
import sys
import contextlib
import json
from collections import defaultdict
from opencage.geocoder import OpenCageGeocode
from dotenv import load_dotenv
import subprocess
import platform
from pyfiglet import figlet_format
from termcolor import colored

# Load environment variables from .env file
load_dotenv()

OPENCAGE_API_KEY = os.getenv('OPENCAGE_API_KEY')

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

def get_location(lat, lon, geocoder_timeout_count, error_messages, retries=3, delay=1):
    """Get city and country from GPS coordinates using OpenCage."""
    geocoder = OpenCageGeocode(OPENCAGE_API_KEY)
    
    for attempt in range(retries):
        try:
            results = geocoder.reverse_geocode(lat, lon, language='en', no_annotations='1')
            if results:
                location = results[0]
                return location['components'], geocoder_timeout_count
        except Exception as e:
            geocoder_timeout_count += 1
            error_messages.append(f"Error for coordinates ({lat}, {lon}) on attempt {attempt + 1}/{retries}: {str(e)}")
            time.sleep(delay)
    
    error_messages.append(f"Geocoder failed after multiple attempts for coordinates ({lat}, {lon}).")
    return None, geocoder_timeout_count

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
    """Round GPS coordinates to reduce redundant Geocoder calls."""
    return round(lat, precision), round(lon, precision)

def count_days_in_cities(data):
    """Count the number of unique days spent in each city and group by country."""
    country_city_days = defaultdict(lambda: defaultdict(set))

    for folder in data['folders']:
        images = folder['images']
        for image in images:
            city = image['city']
            country = image['country']
            date = image['date']
            if city != 'Unknown' and country != 'Unknown' and date != 'Unknown':
                country_city_days[country][city].add(date)

    # Convert sets to counts and find the first visit date for sorting
    country_city_days_count = {}
    for country, cities in country_city_days.items():
        city_days_count = {city: len(dates) for city, dates in cities.items()}
        # Convert date strings to datetime objects for comparison
        first_visit_date = min(datetime.strptime(date, '%Y-%m-%d') for dates in cities.values() for date in dates)
        country_city_days_count[country] = (first_visit_date, city_days_count)

    return country_city_days_count

def generate_summary(data):
    """Generate summary data from the image metadata."""
    country_city_days_count = count_days_in_cities(data)
    
    # Prepare data for JSON output
    countries_data = []
    for country, (first_visit_date, city_days_count) in country_city_days_count.items():
        # Sort cities by visits (descending) and then by name (ascending)
        sorted_cities = sorted(city_days_count.items(), key=lambda x: (-x[1], x[0]))
        
        # Convert cities dictionary to array of objects with consistent property names
        cities_array = []
        for city, days in sorted_cities:
            cities_array.append({
                "name": city,
                "visits": days
            })
        
        # Create country object
        country_obj = {
            "name": country,
            "first_visit_date": first_visit_date.strftime('%Y-%m-%d'),
            "cities": cities_array
        }
        countries_data.append(country_obj)
    
    # Sort countries by first visit date (oldest first) and then by name alphabetically
    countries_data.sort(key=lambda x: (x["first_visit_date"], x["name"]))
    
    # Final output structure
    output_data = {
        "countries": countries_data
    }
    
    return output_data

def save_results(results, summary_data, output_file_base='public/output'):
    """Save the processed data to JSON files."""
    # Save main output file
    main_output_file = f"{output_file_base}.json"
    with open(main_output_file, 'w') as file:
        json.dump(results, file, indent=4)
    print(f"Main data saved to {main_output_file}")
    
    # Save summary output file
    summary_output_file = f"{output_file_base}_summary.json"
    with open(summary_output_file, 'w') as file:
        json.dump(summary_data, file, indent=4)
    print(f"Summary data saved to {summary_output_file}")

def scan_images(directory, precision=1):
    """Scan for images recursively and extract metadata."""
    print("Scanning for images...\n")

    image_paths = glob.glob(os.path.join(directory, '**', '*.jpg'), recursive=True) + \
                  glob.glob(os.path.join(directory, '**', '*.jpeg'), recursive=True) + \
                  glob.glob(os.path.join(directory, '**', '*.JPG'), recursive=True) + \
                  glob.glob(os.path.join(directory, '**', '*.JPEG'), recursive=True)
    
    results = {}
    current_folder = None
    folder_image_count = 0
    folder_index = 0  # Initialize folder-specific index
    total_files = len(image_paths)  # Get total number of images
    processed_files = 0  # Initialize processed files counter
    start_time = time.time()  # Start the timer

    # Initialize elapsed_str to handle cases with no images
    elapsed_str = "0s"

    # Initialize counters
    geocoder_count = 0
    geocoder_error_count = 0
    geocoder_timeout_count = 0
    extracted_exif_count = 0
    exif_error_count = 0

    # Initialize location cache
    location_cache = {}

    # Initialize error messages list
    error_messages = []

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

    max_folder_name_length = 15  # Limit folder name to 15 characters

    for image_path in image_paths:
        folder_name = os.path.basename(os.path.dirname(image_path))
        folder_name_display = (folder_name[:max_folder_name_length] + '...') if len(folder_name) > max_folder_name_length else folder_name

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

        # Estimate remaining time
        if processed_files > 0:
            avg_time_per_file = elapsed_time / processed_files
            remaining_files = total_files - processed_files
            remaining_time = avg_time_per_file * remaining_files
            rem_hours = int(remaining_time // 3600)
            rem_minutes = int((remaining_time % 3600) // 60)
            rem_seconds = int(remaining_time % 60)
            remaining_str = f"{rem_hours}h {rem_minutes}m {rem_seconds}s" if rem_hours > 0 else f"{rem_minutes}m {rem_seconds}s" if rem_minutes > 0 else f"{rem_seconds}s"
        else:
            remaining_str = "Calculating..."

        # Calculate progress percentage
        progress_percentage = (processed_files / total_files) * 100

        # Create a visually appealing progress message
        progress_message = (
            f"\033[1;34m⏳ Time elapsed:\033[0m {elapsed_str}  |  "  # Bold blue time with fixed width
            f"\033[1;31m⏳ Remaining:\033[0m {remaining_str}  |  "  # Bold red remaining time with fixed width
            f"\033[1;35m🌍 Precision:\033[0m {precision} ({precision_accuracy.get(precision, 'Unknown')})  |  "  # Bold magenta precision
            f"\033[1;32m✅ Processed:\033[0m {processed_files}/{total_files} ({progress_percentage:.2f}%)  |  "  # Bold green processed count
            f"\033[1;36m📂 Folder:\033[0m {folder_name_display}  |  "  # Bold cyan folder
            f"\033[1;33m📷 Image:\033[0m {folder_index}/{folder_image_count}"  # Bold yellow image count
        )

        # Print single-line updating message (overwrite previous)
        print('\r' + ' ' * 190, end='\r')  # Clear previous output
        print(progress_message, end='\r', flush=True)  # Overwrite previous line
        
        # Process the image
        try:
            with suppress_stderr():
                tags = get_exif_data(image_path)
            gps = get_gps_coordinates(tags)
            date_taken = get_date_taken(tags)
            if gps or date_taken:
                extracted_exif_count += 1
        except Exception as e:
            exif_error_count += 1
            error_messages.append(f"Error processing {image_path}: {str(e)}")
            continue
        
        location_info = None
        if gps:
            try:
                rounded_gps = round_coordinates(*gps, precision=precision)  # Round the GPS coordinates
                if rounded_gps in location_cache:
                    location_info = location_cache[rounded_gps]  # Use cached location
                else:
                    location_info, geocoder_timeout_count = get_location(*gps, geocoder_timeout_count, error_messages)  # Update geocoder_timeout_count
                    if location_info:
                        location_cache[rounded_gps] = location_info  # Store in cache
                    geocoder_count += 1  # Increment geocoder count
            except Exception as e:
                geocoder_error_count += 1
                error_messages.append(f"Geocoder error for {image_path}: {str(e)}")
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
        "geocoder_calls": geocoder_count,
        "geocoder_errors": geocoder_error_count,
        "geocoder_timeouts": geocoder_timeout_count,
        "original_number_of_files": total_files,
        "files_with_extracted_exif": extracted_exif_count,
        "extracted_exifs_with_errors": exif_error_count
    }
    
    # Convert from dictionary to array format and rename "results" to "folders"
    folders_array = []
    for folder_name, images in results.items():
        folders_array.append({
            "name": folder_name,
            "images": images
        })
    
    # Combine summary, folders, and error messages
    output_data = {
        "summary": summary,
        "folders": folders_array,
        "errors": error_messages
    }
    
    print("\n\nImage scanning complete.")
    
    print(f"Total running time: {elapsed_str}")
    print(f"Geocoder calls made: {geocoder_count}")
    print(f"Geocoder errors: {geocoder_error_count}")
    print(f"Geocoder timeouts: {geocoder_timeout_count}")
    print(f"Original number of files: {total_files}")
    print(f"Files with extracted EXIF: {extracted_exif_count}")
    print(f"Extracted EXIFs with errors: {exif_error_count}\n")
    
    return output_data

def check_valid_json_files(file_paths):
    """Check if all specified JSON files exist and are valid."""
    for file_path in file_paths:
        if not os.path.exists(file_path):
            return False
        try:
            with open(file_path, 'r') as f:
                json.load(f)
        except json.JSONDecodeError:
            return False
    return True

def start_dev_server():
    """Start the development server and display URL."""
    print("\nStarting development server...")

    try:
        # Different approach based on OS
        if platform.system() == "Windows":
            # Windows - redirect to NUL
            npm_process = subprocess.Popen(
                "npm run dev", 
                shell=True, 
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=os.getcwd()
            )
        else:
            # Unix-like systems (Linux/macOS) - redirect to /dev/null
            npm_process = subprocess.Popen(
                "npm run dev", 
                shell=True, 
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=os.getcwd()
            )
        
        # ANSI colour codes for terminal formatting
        ARROW_COLOR = '\033[92m'  # Green
        BASE_COLOR = '\033[36m'   # Teal/cyan
        BOLD_COLOR = '\033[1;36m' # Bold teal/cyan
        RESET = '\033[0m'

        # Format the URL with separate color sections
        formatted_url = f"  {ARROW_COLOR}➜{RESET}  Ready at:   {BASE_COLOR}http://localhost:{BOLD_COLOR}5173{BASE_COLOR}/{RESET}\n"
        
        print(f"Development server started.")
        print(formatted_url)
        print("Press Ctrl+C to stop the server and exit.")
        
        # Keep the script running until interrupted
        npm_process.wait()
        
    except KeyboardInterrupt:
        print("\nStopping development server...")
        npm_process.terminate()
        print("Server stopped.")

def display_app_title():
    """Display ASCII art title for the application using termcolor."""
    print(colored(figlet_format("PicToMap"), color="magenta"))
    print(colored("Photo metadata extraction and mapping tool", color="magenta", attrs=["bold"]), "\n")

if __name__ == "__main__":
    # Display the application title
    display_app_title()
    
    # Define output file paths
    output_file = 'public/output.json'
    summary_file = 'public/output_summary.json'
    
    # Check if files exist and are valid
    files_exist = check_valid_json_files([output_file, summary_file])
    
    # Ask if processing should be redone
    process_again = False
    if files_exist:
        response = input(f"Valid data files found. Process images again? (y/N): ").strip().lower()
        process_again = response in ['y', 'yes']
    else:
        print("No valid data files found. Processing is required.")
        process_again = True
    
    if process_again:
        directory = "/home/alex/Downloads/photos"
        print(f"Starting scan in directory: {directory}")
        image_data = scan_images(directory)
        
        # Generate summary based on the image data
        summary_data = generate_summary(image_data)
        
        # Save both outputs
        save_results(image_data, summary_data, 'public/output')
        
        print("Processing complete.")
    
    # Start the development server
    start_dev_server()
