import styled from "styled-components";

const CityContainer = styled.div`
	margin-left: 20px;
	padding: 5px 0;
`;

const CityName = styled.span`
	font-weight: bold;
	color: #333;
`;

const DaysSpent = styled.span`
	color: #777;
`;

interface CityProps {
	name: string;
	days: number;
}

function City({ name, days }: CityProps) {
	return (
		<CityContainer>
			<CityName>{name}</CityName>: <DaysSpent>{days} day(s)</DaysSpent>
		</CityContainer>
	);
}

export default City;
