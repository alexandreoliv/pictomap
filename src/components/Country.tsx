import styled from "styled-components";
import City from "./City";

const CountryContainer = styled.div`
	background-color: #fff;
	border-radius: 8px;
	box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
	margin-bottom: 20px;
	padding: 15px;
`;

const CountryHeader = styled.h2`
	margin: 0;
	color: #0073e6;
`;

const FirstVisitDate = styled.p`
	color: #555;
	font-size: 0.9em;
`;

interface CityData {
	[city: string]: number;
}

interface CountryProps {
	name: string;
	firstVisitDate: string;
	cities: CityData;
}

function Country({ name, firstVisitDate, cities }: CountryProps) {
	return (
		<CountryContainer>
			<CountryHeader>{name}</CountryHeader>
			<FirstVisitDate>First Visit: {firstVisitDate}</FirstVisitDate>
			{Object.entries(cities).map(([city, days]) => (
				<City key={city} name={city} days={days} />
			))}
		</CountryContainer>
	);
}

export default Country;
