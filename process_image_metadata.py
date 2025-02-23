import json
from collections import defaultdict
from datetime import datetime
import os

def load_json(file_path):
    """Load JSON data from a file."""
    with open(file_path, 'r') as file:
        return json.load(file)

def count_days_in_cities(data):
    """Count the number of unique days spent in each city and group by country."""
    country_city_days = defaultdict(lambda: defaultdict(set))

    for folder, images in data['results'].items():
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

def display_city_days(country_city_days_count):
    """Display the number of days spent in each city, grouped by country."""
    # Sort countries by the first visit date
    sorted_countries = sorted(country_city_days_count.items(), key=lambda x: x[1][0])

    print("Countries and cities with the number of days spent there:")
    for country, (first_visit_date, city_days_count) in sorted_countries:
        # Format the first visit date as a string
        first_visit_date_str = first_visit_date.strftime('%Y-%m-%d')
        print(f"\n{country} (1st visit: {first_visit_date_str}):")
        for city, days in city_days_count.items():
            print(f"  {city}: {days} day(s)")

def save_to_json(country_city_days_count, input_file, output_file_suffix='-summary'):
    """Save the processed data to a JSON file."""
    # Prepare data for JSON output
    output_data = {
        country: {
            "first_visit_date": first_visit_date.strftime('%Y-%m-%d'),  # Convert date to string
            "cities": city_days_count
        }
        for country, (first_visit_date, city_days_count) in country_city_days_count.items()
    }

    # Generate output file name
    base_name = os.path.splitext(input_file)[0]
    output_file = f"{base_name}{output_file_suffix}.json"

    with open(output_file, 'w') as file:
        json.dump(output_data, file, indent=4)
    print(f"\nData saved to {output_file}")

if __name__ == "__main__":
    json_file_path = './data/example-mini.json'

    data = load_json(json_file_path)
    country_city_days_count = count_days_in_cities(data)
    display_city_days(country_city_days_count)
    save_to_json(country_city_days_count, json_file_path) 