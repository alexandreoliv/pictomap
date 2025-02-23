import { useEffect, useState } from "react";
import styled from "styled-components";
import CountryList from "./components/CountryList";

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

interface CityData {
	[city: string]: number;
}

interface CountryData {
	[country: string]: {
		first_visit_date: string;
		cities: CityData;
	};
}

function App() {
	const [data, setData] = useState<CountryData | null>(null);

	useEffect(() => {
		fetch("/example-summary.json")
			.then((response) => response.json())
			.then((data) => setData(data))
			.catch((error) => console.error("Error fetching data:", error));
	}, []);

	return (
		<AppContainer>
			<Title>Image Metadata Viewer</Title>
			{data ? <CountryList countries={data} /> : <p>Loading...</p>}
		</AppContainer>
	);
}

export default App;
