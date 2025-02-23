import { useEffect, useState } from "react";
import styled from "styled-components";
import CountryList from "./components/CountryList";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { LatLngTuple } from "leaflet";

const AppContainer = styled.div`
	font-family: Arial, sans-serif;
	padding: 20px;
	background-color: #f0f4f8;
	min-height: 100vh;
`;

const Title = styled.h1`
	text-align: center;
	color: #333;
`;

interface ImageData {
	filename: string;
	date: string;
	time: string;
	city: string;
	country: string;
	coordinates: [number, number];
}

interface ResultsData {
	[folder: string]: ImageData[];
}

interface SummaryData {
	total_running_time: string;
	geocoder_calls: number;
	geocoder_errors: number;
	geocoder_timeouts: number;
	original_number_of_files: number;
	files_with_extracted_exif: number;
	extracted_exifs_with_errors: number;
}

interface ImageMetadata {
	summary: SummaryData;
	results: ResultsData;
	errors: string[];
}

interface CountrySummary {
	[country: string]: {
		first_visit_date: string;
		cities: {
			[city: string]: number;
		};
	};
}

function App() {
	const [mapData, setMapData] = useState<ImageMetadata | null>(null);
	const [countryData, setCountryData] = useState<CountrySummary | null>(null);

	useEffect(() => {
		// Fetch data for the map
		fetch("/example.json")
			.then((response) => response.json())
			.then((data) => {
				console.log("Fetched map data:", data);
				setMapData(data);
			})
			.catch((error) => console.error("Error fetching map data:", error));

		// Fetch data for the country list
		fetch("/example-summary.json")
			.then((response) => response.json())
			.then((data) => {
				console.log("Fetched country data:", data);
				setCountryData(data);
			})
			.catch((error) =>
				console.error("Error fetching country data:", error)
			);
	}, []);

	// Calculate the center of the map based on the data
	const calculateCenter = (results: ResultsData): LatLngTuple => {
		let minLat = Infinity,
			maxLat = -Infinity,
			minLng = Infinity,
			maxLng = -Infinity;

		Object.values(results)
			.flat()
			.forEach(({ coordinates }) => {
				const [lat, lng] = coordinates;
				if (lat < minLat) minLat = lat;
				if (lat > maxLat) maxLat = lat;
				if (lng < minLng) minLng = lng;
				if (lng > maxLng) maxLng = lng;
			});

		const centerLat = (minLat + maxLat) / 2;
		const centerLng = (minLng + maxLng) / 2;

		return [centerLat, centerLng];
	};

	const mapCenter: LatLngTuple =
		mapData && mapData.results
			? calculateCenter(mapData.results)
			: [51.505, -0.09];

	return (
		<AppContainer>
			<Title>Image Metadata Viewer</Title>
			{mapData && mapData.results ? (
				<MapContainer
					center={mapCenter}
					zoom={2}
					style={{ height: "500px", width: "100%" }}
				>
					<TileLayer
						url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
						attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
					/>
					{Object.values(mapData.results)
						.flat()
						.map((image, index) => (
							<Marker key={index} position={image.coordinates}>
								<Popup>
									<strong>
										{image.city}, {image.country}
									</strong>
									<br />
									{image.date} {image.time}
									<br />
									{image.filename}
								</Popup>
							</Marker>
						))}
				</MapContainer>
			) : (
				<p>Loading map...</p>
			)}
			{countryData ? (
				<CountryList results={countryData} />
			) : (
				<p>Loading country list...</p>
			)}
		</AppContainer>
	);
}

export default App;
