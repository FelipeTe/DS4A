import pandas as pd
import numpy as np
import streamlit as st
import altair as alt
import time
import utils
import os 
import pickle
import joblib

# load model
filename_model = 'acceptance_model.sav'
loaded_model = joblib.load(filename_model)
st.write()

# load colnames
features_colnames_path = 'var_names.pkl'
with open(features_colnames_path, 'rb') as f:
    features_colnames = pickle.load(f)

# data get request
url_request = 'https://webhooks.mongodb-stitch.com/api/client/v2.0/app/getinfocensus-fzwgb/service/getCensusInfo/incoming_webhook/webhook0?'
dict_states = {'Distrito Federal': 'df', 'São Paulo':'sp', 'Sao Paulo':'sp'}

# sidebar
st.sidebar.markdown("""
                # Property approval model

                ## Model inputs

                ### Characteristics of the loan:
                """)

loan_size = st.sidebar.number_input('Loan size (5.000 - 200.000)', min_value=5000, max_value=200000, step=1000, value=7000, format='%.0f')

st.sidebar.markdown("""
                    ### Location of the property:
                    """)

property_address = st.sidebar.text_input('Property Adress', value='R. Itapeva, 636 - Bela Vista')
property_municipality = st.sidebar.selectbox('Property municipality', ['São Paulo'])
property_metropolitan_region = st.sidebar.selectbox('Metropolitan region', ['São Paulo'])

run_button = st.sidebar.button('Get result')
result = st.sidebar.empty()

# main panels
text_description = st.empty()

if run_button:
    # t_rex = st.empty()
    # t_rex.markdown('<iframe width="560" height="315" src="http://wayou.github.io/t-rex-runner/"></iframe>', unsafe_allow_html=True)
    # spinner_ = st.markdown('<div class="container"><h2>Spinners</h2><p>To create a spinner/loader, use the <code>.spinner-border</code> class:</p><div class="spinner-border"></div></div>', unsafe_allow_html=True)
    text_description.empty()

    with st.spinner('Please wait...'):
        progress_bar = st.empty()
        info_progress = st.empty()
        progress_bar.progress(0)
        
        info_progress.text('Geocoding address...')
        property_location = utils.geo_code(property_address, property_municipality+', '+property_metropolitan_region)
        progress_bar.progress(1/6)
        # st.write(property_location)

        info_progress.text('Parsing response...')
        df = pd.DataFrame({'lat': [np.round(property_location['lat'], 5)],  
                        'lon': [np.round(property_location['lng'], 5)]},
                            index=[0])
        lat_long_df = df.rename(columns={'lon': 'long'})
        progress_bar.progress(2/6)
        # st.write(df.head())

        # info_progress.text('Finding corresponding sector code...')
        cod_sector = utils.convert_geo_to_sector_code(property_location, dict_states, '../data/sharp')
        progress_bar.progress(3/6)
        # st.write(cod_sector)

        try:
            info_progress.text('Fetching census information...')
            df_response = pd.read_json('{0:s}sector={1:s}'.format(url_request, cod_sector), orient='records')
            # st.write(df_response)
            df_response = df_response.apply(lambda row: row.apply(lambda cell: utils.flat_cell(cell)))
            df_response = pd.concat([lat_long_df, df_response], axis=1, sort=False)
            df_response = df_response.loc[:, features_colnames]
            # st.write(df_response.columns.tolist())
            # st.write(features_colnames)
            progress_bar.progress(4/6)

            # # make prediction
            info_progress.text('Making prediction...')
            model_result = loaded_model.predict(df_response)
            # st.write(model_result)
            progress_bar.progress(6/6)
            # t_rex.empty()
            progress_bar.empty()
            info_progress.empty()

            st.markdown('**Retrieved street name: **' + property_location['street_name'])
            st.map(df, zoom=14)
            
            if model_result>0.5:
                st.markdown('## Model decision: Accepted')
            else: 
                st.markdown('## Model decision: Rejected')
            
            # st.write(importance_df)

            # percentage
            proba_df_bar = pd.DataFrame({'index': ['Result', 'Result'],
                                     'cat': ['A', 'R'],
                                     'prob': [50, 50]})
            # st.write(proba_df_bar)
            proba_df_circle = pd.DataFrame({'index': 'Result',
                                      'prob': loaded_model.predict_proba(df_response)[:,1]*100},
                                    index=[0])

            # st.write(proba_df_circle)
            proba_plot_bar = alt.Chart(proba_df_bar).mark_bar(opacity=0.8).encode(
                y=alt.Y('index', stack="normalize", axis=alt.Axis(title=None, labels=False, ticks=False)),
                x=alt.X('prob', axis=alt.Axis(title='Probability of acceptance', grid=False)),
                color=alt.Color('cat', legend=None)
            )

            proba_plot_circle = alt.Chart(proba_df_circle).mark_point(color='black', shape='triangle-up').encode(
                        y='index',
                        x='prob'
                        )

            st.altair_chart(proba_plot_bar + proba_plot_circle, use_container_width=True)

            st.markdown('## Features driving the decision')
            # get importance
            
            importance_df = pd.DataFrame({'feature': [col for idx, col in enumerate(features_colnames) if loaded_model['select_model'].get_support()[idx]],
                             'importance': loaded_model['model'].feature_importances_ })

            importance_df['importance'] = np.round(importance_df['importance'], 2)
            importance_df = importance_df.sort_values('importance', ascending=False).head(5)

            plot_alt = alt.Chart(importance_df).mark_bar().encode(
                x=alt.X('importance', axis=alt.Axis(title='Importance', grid=False)),
                y=alt.Y('feature:N', sort='-x', axis=alt.Axis(title=None))
            )

            text_alt = plot_alt.mark_text(
                                align='left',
                                baseline='middle',
                                dx=3  # Nudges text to right so it doesn't appear on top of the bar
                            ).encode(
                                text='importance'
                            )

            complete_alt = (plot_alt + text_alt).properties(height=300)
            st.altair_chart(complete_alt, use_container_width=True)
            st.markdown(
                '''
                The importance of a feature is computed as the (normalized) total reduction of the criterion brought by that feature. It is also known as the Gini importance.[2](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html#sklearn.ensemble.RandomForestClassifier.feature_importances_)

                - **BASICO_V011**: Value of the average monthly nominal income of people aged 10 and over (with income)
                - **BASICO_V009**: Value of the average monthly nominal income of people aged 10 and over (without income)
                - **DOMICILIO_RENDA_V008_pct**: Share of households private with nominal Yield per capita household monthly income of more than 1/2 to minimum wage
                - **DOMICILIO_RENDA_V011_pct**: Share of households private with nominal Yield per capita household monthly income of more than 3 to 5 minimum wages
                - **BASICO_V007**: Value of the average monthly nominal income of people responsible per households permanent private individuals (with income)
                '''
                )
        except:
            st.error('Address not found, please check.')
            # t_rex.empty()
            progress_bar.empty()
            info_progress.empty()
    
    # st.altair_chart(c, use_container_width=True)
else:
    text_description.markdown('''
    ## Information leveraged

    This app takes the address of the property being evaluated and using the census information from the Brazilian Institute for Geography and Statistics -IBGE-
    determines whether or not the request should be approved or not.

    The census is the major reference source to know the life conditions of the population in all the municipalities of Brazil and in their internal
    territorial divisions[1](https://www.ibge.gov.br/en/statistics/social/population/22836-2020-census-censo4.html?=&t=o-que-e).
    
    The Basic Questionnaire of the survey investigates information on:
    
    - The characteristics of the housing units
    - International emigration
    - Composition of the housing units
    - Characteristics of residents
    - Mortality 
    ''')

