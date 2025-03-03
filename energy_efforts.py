import dash
from dash import Dash, html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

# Load and preprocess the data
df = pd.read_csv("cleaned-c02-emissions.csv")
df.fillna(0, inplace=True)
df.dropna(subset=["Country Code"], inplace=True)

# Define indicators
indicators = {
    "EG.ELC.RNEW.ZS": "Renewable electricity output (% of total electricity output)",
    "EG.FEC.RNEW.ZS": "Renewable energy consumption (% of total final energy consumption)",
}

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.LUX])
app.layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                [
                    html.H1(
                        "CO2 Emissions and Renewable Energy Efforts",
                        style={"textAlign": "center"},
                    ),
                    html.H5(
                        id="last-fetched",
                        style={"textAlign": "center", "marginBottom": "20px"},
                    ),
                    dcc.Graph(id="my-choropleth", figure={}),
                ],
                width=12,
            )
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label(
                            "SELECT RENEWABLE ENERGY AREA",
                            className="fw-bold",
                            style={"fontSize": 20},
                        ),
                        dcc.Dropdown(
                            id="dropdown-indicator",
                            options=[{"label": i, "value": i} for i in indicators.values()],
                            value=list(indicators.values())[0],
                            className="me-2",
                        ),
                    ],
                    width=6,
                ),
                dbc.Col(
                    [
                        dbc.Label(
                            "SELECT YEAR:",
                            className="fw-bold",
                            style={"fontSize": 20},
                        ),
                        dcc.Slider(
                            id="year-slider",
                            min=2004,
                            max=2020,
                            step=1,
                            value=2004,
                            marks={year: str(year) for year in range(2004, 2021)},
                        ),
                    ],
                    width=6,
                ),
            ]
        ),
        dcc.Store(id="selected-country"),  # Store selected country
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Country Details")),
                dbc.ModalBody(dcc.Graph(id="country-details")),
                dbc.ModalFooter(
                    dbc.Button("Close", id="close-modal", className="ms-auto", n_clicks=0)
                ),
            ],
            id="details-modal",
            is_open=False,
            size="lg",
        ),
        dcc.Store(id="storage", storage_type="session", data={}),
        dcc.Interval(id="timer", interval=1000 * 60, n_intervals=0),
    ]
)

@app.callback(
    Output("storage", "data"),
    Input("timer", "n_intervals"),
)
def update_storage(n_intervals):
    df = pd.read_csv("cleaned-c02-emissions.csv")
    df.fillna(0, inplace=True)
    df.dropna(subset=["Country Code"], inplace=True)
    return df.to_dict("records")


@app.callback(
    Output("my-choropleth", "figure"),
    Output("selected-country", "data"),  # Store selected country
    Input("year-slider", "value"),
    Input("storage", "data"),
    Input("my-choropleth", "clickData"),  # Capture clicked country
    State("dropdown-indicator", "value"),
)
def update_graph(year_chosen, stored_dataframe, clickData, indct_chosen):
    if not stored_dataframe:
        return px.choropleth(), None

    dff = pd.DataFrame.from_records(stored_dataframe)
    year_column = f"{year_chosen} [YR{year_chosen}]"

    df_co2 = dff[dff["Series Code"] == "EN.ATM.CO2E.PC"]
    df_renewable = dff[dff["Series Name"] == indct_chosen]

    # Merge CO2 and Renewable Energy datasets
    df_merged = pd.merge(
        df_co2[["Country Code", "Country Name", year_column]],
        df_renewable[["Country Code", year_column]],
        on="Country Code",
        suffixes=("_co2", "_renewable"),
    )

    # Add the Combined Score column to the merged dataframe
    df_merged["Combined Score"] = df_merged[f"{year_column}_renewable"] - (
        df_merged[f"{year_column}_co2"] * 1.8
    )

    # Create choropleth figure
    fig = px.choropleth(
        df_merged,
        locations="Country Code",
        color="Combined Score",  # Use Combined Score here
        hover_name="Country Name",
        color_continuous_scale="Greens",
        range_color=[-50, 100],
    )

    # Default zoom and center values
    center = None
    scale = 1

    # If a country is clicked, dynamically zoom and center the map on that country
    if clickData:
        country_code = clickData["points"][0]["location"]
        # Plotly can automatically handle zooming based on country clicked
        # Instead of specifying lat/lon manually, just use country code to focus on it

        fig.update_geos(
            projection_type="natural earth",
            visible=True,
            showcoastlines=True,
            coastlinecolor="White",
            projection_scale=7  # Adjust zoom scale (lower number zooms more)
        )

        # # Optionally, change the zoom factor based on clicked country
        # fig.update_layout(
        #     geo=dict(
        #         center={"lon": 0, "lat": 0},  # Default center, changes on click
        #         projection_scale=7,  # Dynamic zoom level can also be adjusted
        #     )
        # )

    return fig, clickData["points"][0]["location"] if clickData else None



@app.callback(
    Output("country-details", "figure"),
    Output("details-modal", "is_open"),
    Input("selected-country", "data"),
    Input("close-modal", "n_clicks"),
    State("storage", "data"),
    State("dropdown-indicator", "value"),
)
def display_country_details(selected_country, close_clicks, stored_dataframe, indct_chosen):
    if not selected_country or not stored_dataframe or close_clicks > 0:
        return px.line(title="Click a country to see details"), False

    # Convert stored data into a DataFrame
    dff = pd.DataFrame.from_records(stored_dataframe)

    # Get CO₂ emissions data
    df_co2 = dff[(dff["Country Code"] == selected_country) & (dff["Series Code"] == "EN.ATM.CO2E.PC")]

    # Get the selected indicator's data
    df_indicator = dff[(dff["Country Code"] == selected_country) & (dff["Series Name"] == indct_chosen)]

    if df_co2.empty or df_indicator.empty:
        return px.line(title=f"No data available for {selected_country}"), True

    # Extract years dynamically
    year_columns = [col for col in df_co2.columns if "[YR" in col]

    # Reshape both datasets
    df_co2 = df_co2.melt(id_vars=["Country Code"], value_vars=year_columns, var_name="Year", value_name="CO₂ Emissions")
    df_indicator = df_indicator.melt(id_vars=["Country Code"], value_vars=year_columns, var_name="Year", value_name=indct_chosen)

    # Clean up the Year column
    df_co2["Year"] = df_co2["Year"].str.extract(r"(\d{4})").astype(int)
    df_indicator["Year"] = df_indicator["Year"].str.extract(r"(\d{4})").astype(int)

    # Merge both datasets
    df_combined = pd.merge(df_co2, df_indicator, on=["Country Code", "Year"], how="inner")

    # Normalize the data using MinMaxScaler
    scaler = MinMaxScaler()
    df_combined[['CO₂ Emissions Normalized', f'{indct_chosen} Normalized']] = scaler.fit_transform(
        df_combined[['CO₂ Emissions', indct_chosen]]
    )

    # Melt the data to prepare for plotting
    df_final = df_combined.melt(id_vars=["Country Code", "Year"],
                                value_vars=["CO₂ Emissions Normalized", f'{indct_chosen} Normalized'],
                                var_name="Metric", value_name="Value")

    # Custom colors for the lines
    color_map = {
        "CO₂ Emissions Normalized": "orange",
        f'{indct_chosen} Normalized': "green",
    }

    # Create a line chart with both normalized CO₂ and the selected indicator
    fig = px.line(df_final, x="Year", y="Value", color="Metric",
                  title=f"Trends for {selected_country}", markers=False, color_discrete_map=color_map)

    fig.update_layout(
        yaxis=dict(
            range=[0, 1],  # Now the range is from 0 to 1 because of normalization
            tickangle=0,  # Make labels horizontal

        ),
    margin=dict(t=40, r=40, b=300, l=40),  # Increase bottom margin to accommodate horizontal labels

    )

    return fig, True


if __name__ == "__main__":
    app.run_server(debug=True)
