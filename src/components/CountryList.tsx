import styled from "styled-components";
import Country from "./Country";

const ListContainer = styled.div`
	margin: 20px 0;
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

interface CountryListProps {
	countries: CountryData;
}

function CountryList({ countries }: CountryListProps) {
	return (
		<ListContainer>
			{Object.entries(countries).map(
				([country, { first_visit_date, cities }]) => (
					<Country
						key={country}
						name={country}
						firstVisitDate={first_visit_date}
						cities={cities}
					/>
				)
			)}
		</ListContainer>
	);
}

export default CountryList;
