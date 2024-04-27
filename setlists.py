#!/usr/bin/python
# -*- coding: utf-8 -*-

import pandas as pd
from pandas import json_normalize
import requests
import numpy as np
import time
import sys
from bs4 import BeautifulSoup
import re
from datetime import datetime
import plotly.express as px
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import itertools
from itertools import cycle
from ast import literal_eval
from pycountry_convert import country_alpha2_to_continent_code

sys.stdout.reconfigure(encoding='utf-8')            # Fixes encoding problem in Git Bash

'''General data for API requests'''

# MusicBrainz API
base_url = 'http://musicbrainz.org/ws/2/'

params = {            
    'limit': 100,   # Default limit (25) for returned entries increased to maximum (100)
    'fmt':'json'
    }

# Discogs API
with open('../token_discogs') as f:
    token_discogs = f.read()

base_url_d = 'https://api.discogs.com/'

headers_d = {
    'Authorization': f'Discogs token={token_discogs}'
    }

# Setlist.fm API
with open('../api_key_setlist_fm') as f:
    api_key_setlist_fm = f.read()

base_url_sl = 'https://api.setlist.fm/rest/1.0/'

headers_sl = {
    'x-api-key': api_key_setlist_fm,
    'Accept': 'application/json'
    }


'''Search for artist'''

# Get list of artists in accordance with search

while True:
    try:
        artist_name = str(input('Enter an artist name: '))
        print('Searching for an artist...')

        artists = requests.get(f'{base_url}artist/?query=artist:{artist_name}', params=params).json()        
        artists = json_normalize(artists['artists'])[['name', 'disambiguation', 'type', 'life-span.begin', 'id']]
        
        print(artists[['name', 'disambiguation', 'type', 'life-span.begin']].head(25))
        list_len = len(artists.head(25))

    except KeyError:
        print('Sorry, no artists found! Check your input.')
        continue

    break

# Get identifier of artist

while True:
    try:
        index = int(input(f'Enter the row number of an artist (from 0 to {list_len-1}): '))
        artist_id = artists.query('index == @index')['id'].values[0]

    except IndexError:
        print(f'Invalid row number. Please enter a value between 0 and {list_len-1}.')
        continue

    except ValueError:
        print('Invalid input. Please enter a valid integer.')
        continue

    break

'''Get studio albums' tracklists'''

print("Downloading studio albums' tracklists...")

# Get MusicBrainz ids of albums (release groups)
mb_url = f'https://musicbrainz.org/artist/{artist_id}'

try:
    mb_page = requests.get(mb_url) 

except requests.exceptions.ReadTimeout:
    sys.exit('Error! Make sure that https://musicbrainz.org is accessible from your location and try again.')

soup = BeautifulSoup(mb_page.text, 'lxml') 
tags = soup.find('h3', string='Album').next_sibling.find_all('a', attrs={'href': re.compile(r'/release-group/*')})

albums = []                                     # List of MusicBrainz albums' ids

for item in tags:

    id = item.get('href').split('/')[-1]
    albums.append(id)

# Get tracklists of albums
albums_tracklists = []

params['inc'] = 'url-rels'                      # Temporary parameter added to MusicBrainz params

for id in albums:

    while True:
        try: 
            # Get Discogs id of album from related Discogs url (using MusicBrainz API)
            album_id = requests.get(f'{base_url}release-group/{id}', params=params).json()
            album_id = json_normalize(album_id['relations'])
            
            if not album_id.empty and 'discogs' in album_id['type'].unique():

                album_id = album_id.query('type == "discogs"')['url.resource'].to_string().rsplit('/',1)[-1]

                # Get tracklist of album from Discogs
                tracklist = requests.get(f'{base_url_d}/masters/{album_id}', headers=headers_d).json()
                tracklist = json_normalize(tracklist)[['title', 'year', 'tracklist']]

                albums_tracklists.append(tracklist)
        
        except KeyError:
            time.sleep(1)
            continue
    
        break

del params['inc']

tracklists = pd.concat(albums_tracklists)

print('Tracklists downloaded!')

'''Get artist's setlists'''

print('Downloading setlists... Please wait, the process may take several minutes.')

params_sl = {
        'artistMbid': artist_id
    }

# Items per page are limited to 20 in response, so find total number of pages and iterate through them

resp = requests.get(f'{base_url_sl}search/setlists', headers=headers_sl, params=params_sl).json()
total_pages = int(np.ceil(resp['total'] / resp['itemsPerPage']))

setlists = []

for page in range(1, total_pages+1):

    while True:
        try: 
            params_sl = {
                        'artistMbid': artist_id,
                        'p': page
                        }

            setlists_page = requests.get(f'{base_url_sl}search/setlists', headers=headers_sl, params=params_sl).json()  
            setlists_page = json_normalize(setlists_page['setlist'])
            setlists.append(setlists_page)
        
        except KeyError:
            time.sleep(1)
            continue

        break

setlists = pd.concat(setlists)

print('Setlists downloaded!')

'''Data cleaning'''

# Get nested tracklists
tracklists['tracklist'] = tracklists['tracklist'].astype('string').apply(literal_eval)  # Evaluates the string and returns the dictionary object
tracklists = tracklists.explode('tracklist').reset_index(drop=True)                     # Transforms each item of the dictionary to a row (each track is in its own row)
tracks = json_normalize(tracklists['tracklist'])                                        # Flattens nested JSON (new columns added, track names are separated)
tracklists = pd.concat([tracklists, tracks], axis=1)                                    # Joins flattened data to the original dataframe

# Remove & rename columns, replace characters causing problems
tracklists = tracklists.drop(['tracklist', 'position', 'type_', 'duration', 'extraartists'], axis=1)

if 'artists' in tracklists.columns:

    tracklists = tracklists.drop(['artists'], axis=1)

tracklists.columns = ['album', 'release_year', 'song']

tracklists = tracklists.replace({"’": "'"}, regex=True)
tracklists['song'] = tracklists['song'].str.replace("&", "and")   

# Get nested setlists
# Need to explode data twice because of the Encore sections of set 
temp_setlists = setlists.copy()                                                 
temp_setlists['sets.set'] = temp_setlists['sets.set'].astype('string').apply(literal_eval)       
temp_setlists = temp_setlists.explode('sets.set').reset_index(drop=True)        # Each set is exloded to main part + encore(s) rows with nested songs

songs = json_normalize(temp_setlists['sets.set'])                               # Songs are separated from Encore tags
songs = pd.concat([songs, temp_setlists['id']], axis=1)                         # Setlist 'id' is required to merge songs and setlists later
songs = songs.explode('song').reset_index(drop=True)                            # Each song is in its own row

# Some songs are played from the tapes (e.g. intros), so remove these non-live songs
songs['song'] = songs['song'].astype('string')
tapes_list = songs.query('song.str.contains("\'tape\': True", case=False)').index.to_list()      
songs = songs.query('index not in @tapes_list')

# Parse song names
songs['song'] = songs['song'].apply(lambda x: str(x).split(',')[0].split(':')[1].strip("} ").strip("'").strip("\"") if pd.notna(x) else x).astype('string')
songs['song'] = songs['song'].str.replace("&", "and")

# Merge setlists and songs
setlists = setlists.merge(songs[['id', 'song']], how='left', on='id')

# Remove & rename columns
setlists = setlists.drop(['versionId', 'lastUpdated', 'artist.mbid', 'artist.sortName', 'artist.disambiguation', 
                          'artist.url', 'venue.city.id', 'venue.city.state', 'venue.city.stateCode', 'sets.set', 'info'], axis=1)

setlists.rename(columns={'id': 'setlist_id', 'eventDate': 'event_date', 'artist.name': 'artist', 'tour.name': 'tour',
                         'venue.id':'venue_id', 'venue.name': 'venue', 'venue.url': 'venue_url', 
                         'venue.city.name': 'city', 'venue.city.coords.lat': 'city_latitude', 'venue.city.coords.long': 'city_longitude',
                         'venue.city.country.code': 'country_code', 'venue.city.country.name': 'country'},inplace=True)

artist = setlists['artist'].unique()[0]                         # Returns artist name

# Remove duplicate rows
tracklists = tracklists.drop_duplicates(keep='last').reset_index(drop=True)
setlists = setlists.drop_duplicates(keep='last').reset_index(drop=True)

# Merge setlists and tracklists
setlists = setlists.merge(tracklists, how='left', left_on=setlists['song'].str.lower(), right_on=tracklists['song'].str.lower())

setlists = setlists.drop(['song_y', 'key_0'], axis=1)
setlists.rename(columns={'song_x': 'song'}, inplace=True)

# Mark non-album songs as '-Other-'
setlists['album'] = np.where((setlists['album'].isna()) & (setlists['song'].notna()), '-Other-', setlists['album'])    

# Change data types
for c in setlists.select_dtypes(include='object').columns:

    setlists[c] = setlists[c].astype('string')

setlists['event_date'] = pd.to_datetime(setlists['event_date'], format='%d-%m-%Y')
setlists['event_year'] = setlists['event_date'].dt.year.astype('Int64')                     # New column 'event_year' added 
setlists['release_year'] = setlists['release_year'].astype('Int64') 

# Filter out future and today dates
today = datetime.today().date()
setlists = setlists.query('event_date < @today').reset_index(drop=True)

'''Data Interpretation and Visualization'''

# Create dictionary with commom labels for plots
labels_dict={'year':'Year', 
             'event_year': 'Year',
             'month':'Month',
             'day':'Day of the Week',
             'continent': 'Continent',
             'country':'Country',
             'city':'City',
             'album': 'Album',
             'song':'Song', 
             'percentage': 'Percentage'}

# Create dictionary with legend items for plots
albums_list = tracklists[['album', 'release_year']].drop_duplicates()
albums_list['album+release_year'] = albums_list['album'] + ' (' + albums_list['release_year'].astype('string') + ')'

legend_items_names=dict(zip(albums_list['album'], albums_list['album+release_year']))
legend_items_names['-Other-'] = '-Other-'

# Save plot to .html file
def save_to_html(fig, full_title):

    fig.write_html(f'{full_title}.html', 
               auto_open=True)   

# Group events by years
def group_by_years():

    by_years = (setlists.groupby('event_year', as_index=False) 
                        .agg(count=('setlist_id', 'nunique'))
                )

    # Create full list of years (w/o gaps)
    years_list = pd.DataFrame(data=range(by_years['event_year'].min(), by_years['event_year'].max()+1), columns=['year'])

    by_years = years_list.merge(by_years, how='left', left_on='year', right_on='event_year')[['year', 'count']].fillna(0)

    by_years['count'] = by_years['count'].astype('int64')
    by_years['percentage'] = (by_years['count'] / by_years['count'].sum() * 100).round(1).astype('string')+'%'

    title = f'{artist} - Distribution of Events by Year'

    return by_years, title

# Create bar plot for distribution of events by year
def bar_by_years():

    labels_dict['count'] = 'Number of Events'

    fig = px.bar(
                group_by_years()[0], 
                x='year', 
                y='count', 
                color='count', 
                color_continuous_scale='Aggrnyl',
                labels=labels_dict,
                text_auto=True,
                hover_name='year',
                hover_data={'percentage': True, 'year': False}
                )

    fig.update_layout(
                    title=dict(text=f'<b>{group_by_years()[1]}</b>', 
                               x=0.5), 
                    xaxis=dict(dtick=1,
                               tickangle=45),
                    coloraxis_showscale=False
                    )

    # Add annotation for album release years
    y = ['1.03', '0.99']

    for year, y in zip(tracklists['release_year'].unique(), cycle(y)):

        # print(year, y)
        fig.add_vline(
                    x=year, 
                    annotation_text=tracklists.query('release_year == @year')['album'].unique()[0],
                    annotation_y=y,
                    line=dict(width=1, dash='dot', color='grey')
                    )

    return save_to_html(fig, group_by_years()[1])

# Group events by months
def group_by_months():

    # Add 'continent' column
    # 'AQ' code (Antarctica) is missing in the converter
    setlists['continent'] = setlists['country_code'].apply(lambda x: country_alpha2_to_continent_code(x) if x != 'AQ' else 'AN')

    continent_names = {
                    'AF': 'Africa',
                    'AN': 'Antarctica',
                    'AS': 'Asia',
                    'EU': 'Europe',
                    'NA': 'North America',
                    'OC': 'Oceania',
                    'SA': 'South America'
                    }

    setlists['continent'] = setlists['continent'].map(continent_names)

    # Group data
    by_months = (setlists.groupby(by=[setlists['event_date'].dt.month,
                                      setlists['event_date'].dt.month_name(),
                                      'continent'])
                         .agg(count=('setlist_id', 'nunique'))
                )

    by_months.index.names = ['month_num', 'month', 'continent']
    by_months = by_months.reset_index().sort_values(by=['month_num'])

    # Data for additional plot trace
    months_total = by_months.groupby(by=['month_num', 'month'])['count'].sum().reset_index()
    months_total['percentage'] = (months_total['count'] / months_total['count'].sum() * 100).round(1).astype('string')+'%'
    months_total['count+percentage'] = months_total['count'].astype('string') + ' (' + months_total['percentage']+')'

    title = f'{artist} - Distribution of Events by Month'

    return by_months, title, months_total

# Create bar plot for distribution of events by month
def bar_by_months():

    labels_dict['count'] = 'Number of Events'
    sorted_continents = group_by_months()[0].groupby('continent')['count'].sum().sort_values(ascending=False).index.to_list()

    fig = px.bar(
                group_by_months()[0], 
                x='month', 
                y='count', 
                color='continent', 
                category_orders={'continent': sorted_continents},
                color_discrete_sequence=px.colors.qualitative.Bold,
                labels=labels_dict,
                text_auto=True,
                hover_name='month',
                hover_data={'month': False}
                )

    fig.update_traces(textposition='inside')

    fig.add_trace(go.Scatter(
                    x=group_by_months()[2]['month'], 
                    y=group_by_months()[2]['count'],
                    text=group_by_months()[2]['count+percentage'],
                    mode='text',
                    textposition='top center',
                    textfont=dict(size=13, family='Verdana Black'),
                    showlegend=False,
                    name = '')
                )

    fig.update_layout(
                    title=dict(text=f'<b>{group_by_months()[1]}</b>', 
                               x=0.5)
                    )

    return save_to_html(fig, group_by_months()[1])

# Group events by days of the week
def group_by_days_of_week():

    by_days_of_week = (setlists.groupby(by=[setlists['event_date'].dt.dayofweek,
                                            setlists['event_date'].dt.day_name()])
                               .agg(count=('setlist_id', 'nunique'))
                        )

    by_days_of_week.index.names = ['day_num', 'day']
    by_days_of_week = by_days_of_week.reset_index().sort_values(by=['day_num'])
    by_days_of_week['percentage'] = (by_days_of_week['count'] / by_days_of_week['count'].sum() * 100).round(1).astype('string')+'%'

    title = f'{artist} - Distribution of Events by Day of the Week'

    return by_days_of_week, title

# Create bar plot for distribution of events by days of the week
def bar_by_days_of_week():

    labels_dict['count'] = 'Number of Events'

    fig = px.bar(
                group_by_days_of_week()[0], x='day', y='count', 
                color_discrete_sequence=['#592941'],
                color='day',
                color_discrete_map={'Saturday' : '#52B788',
                                    'Sunday' : '#52B788'},
                labels=labels_dict,
                text_auto=True,
                hover_name='day',
                hover_data={'percentage': True, 'day': False}
                )

    fig.update_traces(textposition='outside')

    fig.update_layout(
                    title=dict(text=f'<b>{group_by_days_of_week()[1]}</b>', 
                               x=0.5),
                    showlegend=False
                    )

    return save_to_html(fig, group_by_days_of_week()[1])

# Group events by countries
def group_by_countries():

    by_countries = (setlists.groupby(['country', 'country_code'], as_index=False) 
                            .agg(count=('setlist_id', 'nunique'))
                            .sort_values(by=['count', 'country'], ascending=[False, True])
                    )
                    
    by_countries['percentage'] = (by_countries['count'] / by_countries['count'].sum() * 100).round(1).astype('string')+'%'

    title = f'{artist} - Top 30 Countries by Number of Events'
    title_map = f'{artist} - Distribution of Events by Country on Map'

    return by_countries, title, title_map

# Create bar plot for distribution of events by country (Top 30)
def bar_by_countries():

    labels_dict['count'] = 'Number of Events'

    fig = px.bar(
            group_by_countries()[0].head(30), 
            x='country', 
            y='count',   
            color='count', 
            color_continuous_scale='Viridis',
            labels=labels_dict,
            text_auto=True,
            hover_name='country',
            hover_data={'percentage': True, 'country': False}
                )

    fig.update_traces(textposition='outside')
            
    fig.update_layout(
                    title=dict(text=f'<b>{group_by_countries()[1]}</b>', 
                               x=0.5),
                    xaxis_tickangle=45,
                    coloraxis_showscale=False
                    )

    return save_to_html(fig, group_by_countries()[1])

# Create choropleth plot for distribution of events by country on map
def map_by_countries():

    labels_dict['count'] = 'Number of Events'
    geo_countries = requests.get('https://geojson.xyz/naturalearth-3.3.0/ne_50m_admin_0_countries.geojson').json()  

    fig = px.choropleth_mapbox(
                            data_frame=group_by_countries()[0],
                            geojson=geo_countries,
                            featureidkey='properties.iso_a2',
                            locations='country_code',
                            color='count',
                            color_continuous_scale='Viridis',
                            opacity=0.8,
                            center=dict(lat=28.0, lon=23.0),
                            zoom=1.5,
                            labels=labels_dict,
                            hover_name='country',
                            hover_data={'percentage': True, 'country_code': False}
                            )

    fig.update_layout(
                    mapbox_style='open-street-map',
                    margin={'r':0, 'l':0,'b':0},
                    title=dict(text=f'<b>{group_by_countries()[2]}</b>', 
                               x=0.5)
                    )
    
    return save_to_html(fig, group_by_countries()[2])

# Group events by cities
def group_by_cities():

    by_cities = (setlists.groupby(['city', 'city_latitude', 'city_longitude', 'country'], as_index=False) 
                     .agg(count=('setlist_id', 'nunique'))
                     .sort_values(by=['count', 'city'], ascending=[False, True]))

    by_cities['percentage'] = (by_cities['count'] / by_cities['count'].sum() * 100).round(1).astype('string')+'%'

    title = f'{artist} - Top 30 Cities by Number of Events'
    title_map = f'{artist} - Distribution of Events by City on Map'

    return by_cities, title, title_map

# Create bar plot for distribution of events by city (Top 30)
def bar_by_cities():

    labels_dict['count'] = 'Number of Events'

    fig = px.bar(
                group_by_cities()[0].head(30), 
                x='city',
                y='count',
                color='count',
                color_continuous_scale='Viridis',
                labels=labels_dict,
                text_auto=True,
                hover_name='city',
                hover_data={'percentage': True, 'country': True, 'city': False}
                )

    fig.update_traces(textposition='outside')
                
    fig.update_layout(
                    title=dict(text=f'<b>{group_by_cities()[1]}</b>', 
                               x=0.5),
                    xaxis_tickangle=45,
                    coloraxis_showscale=False
                    )
    
    return save_to_html(fig, group_by_cities()[1])

# Create scatter plot for distribution of events by city on map
def map_by_cities():

    labels_dict['count'] = 'Number of Events'

    fig = px.scatter_mapbox(
                            group_by_cities()[0], 
                            lat='city_latitude', 
                            lon='city_longitude', 
                            color='count', 
                            size='count', 
                            color_continuous_scale='Viridis',
                            opacity=0.8,
                            center=dict(lat=48.0, lon=13.0),
                            zoom=4, 
                            labels=labels_dict,
                            hover_name='city',
                            hover_data={'percentage': True, 'country': True, 'city_latitude': False, 'city_longitude': False}
                            )

    fig.update_layout(
                    mapbox_style='open-street-map',
                    margin={'r':0, 'l':0,'b':0},
                    title=dict(text=f'<b>{group_by_cities()[2]}</b>', 
                               x=0.5))
    
    return save_to_html(fig, group_by_cities()[2])

# Get setlists size (number of songs played during a single event)
def get_setlists_size():

    # All setlists' size
    setlists_size = (setlists.groupby(by='setlist_id', as_index=False)
                             .agg(count=('song', 'count')))

    # Filled setlists' size (remove empty setlists)
    filled_setlists_size = setlists_size.query('count > 0')

    title_hist = f'{artist} - Distribution of Setlists Size'
    title_violin = f'{artist} - Distribution of Filled Setlists Size on Violin Plot'

    return setlists_size, title_hist, filled_setlists_size, title_violin

# Create histogram for distribution of setlists' size
def hist_setlists_size():

    labels_dict['count'] = 'Number of Songs'

    fig = px.histogram(
                    get_setlists_size()[0], 
                    x='count',
                    color_discrete_sequence=px.colors.qualitative.Dark2,
                    labels=labels_dict
                    )

    fig.update_traces(hovertemplate='Number of Songs=%{x}<br>Frequency (Number of Setlists)=%{y}')

    fig.update_layout(title=dict(text=f'<b>{get_setlists_size()[1]}</b>', 
                                x=0.5), 
                    xaxis_dtick=1,
                    yaxis_title='Frequency')
    
    return save_to_html(fig, get_setlists_size()[1])

# Create violin plot for distribution of filled setlists' size
def violin_filled_setlists_size():

    labels_dict['count'] = 'Number of Songs'

    fig = px.violin(
                    get_setlists_size()[2], 
                    y='count',
                    box=True,
                    color_discrete_sequence=px.colors.qualitative.Dark2,
                    labels=labels_dict
                    )

    fig.update_layout(title=dict(text=f'<b>{get_setlists_size()[3]}</b>', 
                                x=0.5))
    
    return save_to_html(fig, get_setlists_size()[3])

# Get only filled setlists (remove empty setlists)
def get_filled_setlists():

    filled_setlists_ids = get_setlists_size()[2]['setlist_id'].unique()
    filled_setlists = setlists.query('setlist_id in @filled_setlists_ids')

    return filled_setlists, filled_setlists_ids

# Group events by songs
def group_by_songs():

    by_songs = (get_filled_setlists()[0].groupby(['album','release_year', 'song'], dropna=False, as_index=False) 
                                        .agg(count=('setlist_id', 'nunique'))
                                        .sort_values(by=['count', 'song'], ascending=[False, True]))

    by_songs['percentage'] = (by_songs['count'] / len(get_filled_setlists()[1]) * 100).round(1).astype('string')+'%'

    title = f'{artist} - Top 30 Played Songs'
    title_pie = f'{artist} - Shares of Album Songs in Setlists'

    return by_songs, title, title_pie

# Create plot for the most played songs (Top 30)
def bar_by_songs():

    labels_dict['count'] = 'Times Played'
    color_map = dict(zip(group_by_songs()[0]['album'].unique(), px.colors.qualitative.Bold))

    fig = px.bar(
                group_by_songs()[0].head(30), 
                x='count', 
                y='song',
                orientation='h', 
                color='album', 
                color_discrete_map=color_map,
                labels=labels_dict,
                text_auto=True,
                hover_name='song',
                hover_data={'percentage': True, 'song': False}
                )
    
    fig.for_each_trace(lambda t: t.update(name=legend_items_names[t.name]))

    fig.update_layout(
                    title=dict(text=f'<b>{group_by_songs()[1]}</b>', 
                               x=0.5),
                    yaxis_autorange='reversed',
                    yaxis_dtick=1)

    return save_to_html(fig, group_by_songs()[1])

# Create pie plot with shares of album songs
def pie_by_songs():

    color_map = dict(zip(group_by_songs()[0]['album'].unique(), px.colors.qualitative.Bold))

    fig = make_subplots(rows=1, cols=1, specs=[[{'type': 'pie'}]])

    common_props = dict(
                        labels=group_by_songs()[0]['album'].map(legend_items_names),
                        values=group_by_songs()[0]['count'], 
                        marker_colors = group_by_songs()[0]['album'].map(color_map),
                        name = '',
                        sort=True, 
                        direction='clockwise'
                        )

    fig.add_trace(go.Pie(
                    common_props,                
                    textinfo='label',
                    textposition='outside'
                        ), 
                    row=1, col=1)

    fig.add_trace(go.Pie(
                    common_props,
                    textinfo='value+percent',
                    textposition='inside'
                        ), 
                    row=1, col=1)

    fig.update_layout(
                    title=dict(text=f'<b>{group_by_songs()[2]}</b>', 
                               x=0.5))

    return save_to_html(fig, group_by_songs()[2])

# Group songs by albums played over the years
def group_by_albums():

    albums_by_years = (get_filled_setlists()[0].groupby(by=['album', 'event_year', 'release_year'], dropna=False, as_index=False)
                                               .agg(count=('song', 'count'))
                                               .sort_values(by=['release_year', 'event_year'])
                        )

    albums_by_years['percentage'] = ((albums_by_years['count'] / albums_by_years['event_year']
                                            .apply(lambda x: albums_by_years.query('event_year == @x')['count'].sum()) * 100).round(1))

    albums_by_years['count+percentage'] = albums_by_years['count'].astype('string') + ' (' + albums_by_years['percentage'].astype('string')+'%)'

    title = f'{artist} - Albums Played Over the Years'

    return albums_by_years, title

# Group songs by albums played over the years
# Add rows with count=0 for years when album was not played (for hover data of area plot)
def group_by_albums_full():

    # Cartesian product of albums X event years 
    cartesian_product_list = list(itertools.product(group_by_albums()[0]['album'].unique(), 
                                                    group_by_albums()[0]['event_year'].unique()))

    cartesian_product = pd.DataFrame(data=cartesian_product_list, 
                                    columns=['album', 'event_year'])

    # Add rows with count=0 for albums not played during the specific year
    albums_by_years_full = (cartesian_product.merge(group_by_albums()[0][['album', 'event_year', 'count']], how='left', on=['album','event_year']).fillna(0)
                                             .merge(group_by_albums()[0][['album', 'event_year', 'release_year']], how='left', on=['album','event_year'])
                                             .sort_values(by=['release_year']))
                        
    albums_by_years_full['count'] = albums_by_years_full['count'].astype('Int64')

    albums_by_years_full['percentage'] = ((albums_by_years_full['count'] / albums_by_years_full['event_year']
                                            .apply(lambda x: albums_by_years_full.query('event_year == @x')['count'].sum()) * 100).round(1))

    albums_by_years_full['count+percentage'] = albums_by_years_full['count'].astype('string') + ' (' + albums_by_years_full['percentage'].astype('string')+'%)'

    title = f'{artist} - Shares of Albums Played Over the Years'

    return albums_by_years_full, title

# Create line plot for albums played over the years
def line_by_albums():

    labels_dict['count+percentage'] = 'Songs from Album Played'
    color_map = dict(zip(group_by_songs()[0]['album'].unique(), px.colors.qualitative.Bold))

    fig = px.line(
                group_by_albums()[0], 
                x='event_year', 
                y='count', 
                color='album', 
                color_discrete_map = color_map, 
                labels=labels_dict,
                markers=True,
                hover_data={'count+percentage': True,
                            'event_year': False, 
                            'count': False}
                )

    # Add annotation for album release years
    y = ['1.03', '0.99']

    for year, y in zip(tracklists['release_year'].unique(), cycle(y)):

        fig.add_vline(
                    x=year, 
                    annotation_text=tracklists.query('release_year == @year')['album'].unique()[0],
                    annotation_y=y,
                    line=dict(width=1, dash='dot', color='grey')
                    )

    fig.for_each_trace(lambda t: t.update(name=legend_items_names[t.name]))

    fig.update_layout(title=dict(text=f'<b>{group_by_albums()[1]}</b>', 
                                x=0.5), 
                    xaxis_dtick=1,
                    xaxis_tickangle=45,
                    yaxis_title='Songs Played',
                    hovermode='x unified')

    return save_to_html(fig, group_by_albums()[1])

# Create area plot for albums played over the years
def area_by_albums():

    labels_dict['count+percentage'] = 'Songs from Album Played'
    color_map = dict(zip(group_by_songs()[0]['album'].unique(), px.colors.qualitative.Bold))

    fig = px.area(
                group_by_albums_full()[0], 
                x='event_year',
                y='count',
                color='album',
                color_discrete_map = color_map,
                labels=labels_dict,
                groupnorm='percent',
                hover_data={'count+percentage': True,
                            'event_year': False, 
                            'count': False}, 
                )

    # Add annotation for album release years
    y = ['1.03', '0.99']

    for year, y in zip(tracklists['release_year'].unique(), cycle(y)):

        fig.add_vline(
                    x=year, 
                    annotation_text=tracklists.query('release_year == @year')['album'].unique()[0],
                    annotation_y=y,
                    line=dict(width=1, dash='dot', color='grey')
                    )

    fig.for_each_trace(lambda t: t.update(name=legend_items_names[t.name]))

    fig.update_layout(
                    title=dict(text=f'<b>{group_by_albums_full()[1]}</b>', 
                                x=0.5), 
                    xaxis_dtick=1,
                    xaxis_tickangle=45,
                    yaxis_title='Songs Played (%)',
                    hovermode='x unified'             
                    )

    return save_to_html(fig, group_by_albums_full()[1])

# Get never played or rarely played songs from official albums
def get_rare_songs():
    
    tracklists_with_counts = (tracklists.merge(
                                            group_by_songs()[0][['song', 'count']], 
                                            how='left', 
                                            left_on=tracklists['song'].str.lower(), 
                                            right_on=group_by_songs()[0]['song'].str.lower())[['album', 'release_year', 'song_x', 'count']]
                                        .fillna(0)
                                        .rename(columns={'song_x': 'song'}))

    tracklists_with_counts['count'] = tracklists_with_counts['count'].astype('Int64')   
    tracklists_with_counts = tracklists_with_counts[['song', 'album', 'release_year', 'count']].sort_values(by=['count', 'release_year'])

    return tracklists_with_counts

# Get top 5 first and last songs of setlists
def get_edge_songs():

    first_last_songs = (get_filled_setlists()[0].groupby('setlist_id', as_index=False)
                                                .agg(first_song=('song', 'first'), last_song=('song', 'last'), count=('song', 'count'))
                                                .query('count > 1')                    # Removes setlists with only one song
                                                )      
    def songs_share(type):

        edge_songs = (first_last_songs.groupby(type)
                                      .agg(count=('setlist_id', 'count'))
                                      .sort_values(by='count', ascending=False)
                                      .reset_index())
        
        edge_songs['percentage'] = (edge_songs['count'] / edge_songs['count'].sum() * 100).round(1).astype('string')+'%'

        return edge_songs

    return songs_share('first_song'), songs_share('last_song')
    
'''User Requests'''

available_data = {
                1: 'General Data about Setlists', 
                2: '(Chart) Events by Year', 
                3: '(Chart) Events by Month', 
                4: '(Chart) Events by Country on Map', 
                5: '(Chart) Events by City on Map', 
                6: '(Chart) Top 30 Played Songs', 
                7: '(Chart) Top 30 Visited Countries', 
                8: '(Chart) Top 30 Visited Cities', 
                9: '(Chart) Shares of Album Songs in Setlists', 
                10: '(Chart) Albums Played Over the Years', 
                11: '(Chart) Shares of Albums Played Over the Years', 
                12: '(Chart) Events by Day of the Week', 
                13: '(Chart) Setlists Size', 
                14: '(Chart) Filled Setlists Size', 
                15: 'Never Played Album Songs', 
                16: 'Rarely Played Album Songs', 
                17: 'Top 15 Non-Album Songs Played', 
                18: 'Top 5 First and Last Songs', 
                19: 'Table Data for Charts',
                20: 'Exit'
                }

available_data = pd.DataFrame.from_dict(available_data, orient='index', columns=['Info']) 

def get_answer():

    answer = str(input('Do you want to get some other info? y/n '))
    print()

    return answer
            
while True:
    try:                                       
        
        print('\n What info do you want to get? \n')
        print('* Charts will be saved to your computer in the .html format and opened automatically in your browser.\n')
        print(available_data, '\n')
        user_request = int(input(f'Please enter the row number from 1 to {len(available_data)}. '))      
        print()

        if user_request == 1:

            # General Data

            print(artist, '\n')
            print(f"Years on Tour: {len(group_by_years()[0].query('count > 0'))} (from {group_by_years()[0]['year'].min()} to {group_by_years()[0]['year'].max()})")
            print(f'Visited Countries: {len(group_by_countries()[0])}')
            print(f'Visited Cities: {len(group_by_cities()[0])}')
            print(f'Events: {len(get_setlists_size()[0])}')                                    
            print(f'Filled Setlists: {len(get_setlists_size()[2])}')
            empty_setlists = len(get_setlists_size()[0])-len(get_setlists_size()[2])
            print(f'Empty Setlists: {empty_setlists} ({empty_setlists / len(get_setlists_size()[0]):.1%})')
            print(f"Median Number of Songs for Filled Setlists: {int(get_setlists_size()[2]['count'].median())}", '\n')
           
            if get_answer() != 'n': 
                continue

        elif user_request == 2:

            bar_by_years()
           
            if get_answer() != 'n': 
                continue

        elif user_request == 3:

            bar_by_months()

            if get_answer() != 'n': 
                continue

        elif user_request == 4:

            map_by_countries()

            if get_answer() != 'n': 
                continue

        elif user_request == 5:

            map_by_cities()

            if get_answer() != 'n': 
                continue

        elif user_request == 6:

            bar_by_songs()

            if get_answer() != 'n': 
                continue

        elif user_request == 7:

            bar_by_countries()

            if get_answer() != 'n': 
                continue

        elif user_request == 8:

            bar_by_cities()

            if get_answer() != 'n': 
                continue

        elif user_request == 9:

            pie_by_songs()

            if get_answer() != 'n': 
                continue

        elif user_request == 10:

            line_by_albums()

            if get_answer() != 'n': 
                continue

        elif user_request == 11:

            area_by_albums()

            if get_answer() != 'n': 
                continue
        
        elif user_request == 12:

            bar_by_days_of_week()

            if get_answer() != 'n': 
                continue

        elif user_request == 13:

            hist_setlists_size()

            if get_answer() != 'n': 
                continue

        elif user_request == 14:

            violin_filled_setlists_size()

            if get_answer() != 'n': 
                continue

        elif user_request == 15:

            print(f'{artist}: Album Songs Never Played Live', '\n')
            print(get_rare_songs().query('count == 0'), '\n')

            if get_answer() != 'n': 
                continue

        elif user_request == 16:

            print(f'{artist}: Album Songs Rarely Played Live (less than 4 times)', '\n')
            print(get_rare_songs().query('count != 0 and count <= 3'), '\n')

            if get_answer() != 'n': 
                continue

        elif user_request == 17:

            print(f'{artist}: Top 15 Non-Album Songs Played', '\n')
            print(group_by_songs()[0].query('album == "-Other-"').head(15), '\n')

            if get_answer() != 'n': 
                continue

        elif user_request == 18:
        
            print(f'{artist} - Number of first songs: {len(get_edge_songs()[0])} \n\n', \
                'Top 5 First Songs: \n', get_edge_songs()[0].head(), '\n')
            print(50*'-', '\n')
            print(f'{artist} - Number of last songs: {len(get_edge_songs()[1])} \n\n', \
                'Top 5 Last Songs: \n', get_edge_songs()[1].head(), '\n')
            
            if get_answer() != 'n': 
                continue

        elif user_request == 19:

            # Events by Year
            print(group_by_years()[1], '\n')
            print(group_by_years()[0])
            print(50*'-', '\n')

            # Events by Month
            print(group_by_months()[1], '\n')
            print(group_by_months()[2][['month', 'count', 'percentage']])
            print(50*'-', '\n')

            # Events by Days of the Week
            print(group_by_days_of_week()[1], '\n')
            print(group_by_days_of_week()[0][['day', 'count', 'percentage']])
            print(50*'-', '\n')

            # Events by Countries
            print(group_by_countries()[1], '\n')
            print(group_by_countries()[0][['country', 'count', 'percentage']].head(30))
            print(50*'-', '\n')

            # Events by Cities
            print(group_by_cities()[1], '\n')
            print(group_by_cities()[0][['city', 'count', 'percentage']].head(30))
            print(50*'-', '\n')

            # Events by Songs
            print(group_by_songs()[1], '\n')
            print(group_by_songs()[0][['song', 'album', 'release_year', 'count', 'percentage']].head(30))
            print(50*'-', '\n')

            if get_answer() != 'n': 
                continue

        elif user_request == 20:
        
            break

        else:
            print('!!! Invalid row number. Please try again.')
            continue

    except ValueError:
        print(f'!!! Invalid row number. Please try again.')
        continue

    except KeyError:
        print(f'!!! Internal error. Choose some other info.')
        continue

    break