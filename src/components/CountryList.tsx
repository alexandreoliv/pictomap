import styled from "styled-components";
import Country from "./Country";

const ListContainer = styled.div`
	margin: 20px 0;
`;

interface City {
	name: string;
	visits: number;
}

interface Country {
	name: string;
	first_visit_date: string;
	cities: City[];
}

interface CountrySummary {
	countries: Country[];
}

interface CountryListProps {
	results: CountrySummary;
}

function CountryList({ results }: CountryListProps) {
	return (
		<ListContainer>
			{results.countries.map((country) => (
				<Country
					key={country.name}
					name={country.name}
					firstVisitDate={country.first_visit_date}
					cities={country.cities}
				/>
			))}
		</ListContainer>
	);
}

export default CountryList;
