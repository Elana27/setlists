# setlists

Have you ever wondered how many countries your favourite band has visited? Or which songs they have never played live? Or how many years they have been on tour? 

The 'setlists.py' script can help. This script allows you to analyze events and setlists of any music artist.

>A set list, or **setlist**, is typically a document that lists the songs that a band or musical artist intends to play / played during a specific concert performance.

## How to Use the Script

**NOTE:** For this script to work, you need to **get your own** API Key for Setlist.fm and token for Discogs (IT'S FREE). 

1. Get **API Key for Setlist.fm**:
    - Create an account at [Setlist.fm](https://www.setlist.fm/signup).
    - Apply for an API Key on the [Settings](https://www.setlist.fm/settings/apps) page: provide Application Name and Application Description of your choice, agree to comply with the Terms of Service and click the *'Submit'* button.
    - Your API key will be immediately available on the [Settings](https://www.setlist.fm/settings/apps) page. 

2. Get **Token for Discogs**:
    - Create an account at [Discogs](https://login.discogs.com/u/signup?state=hKFo2SAwWk9CaUJZSng3VF8tU2hFdDZ3N2cyem1wa0NLcTJwbKFur3VuaXZlcnNhbC1sb2dpbqN0aWTZIFhINW9vOTh3R19MbkpGTTRGNkdiTmtnblZtTHh0MFJBo2NpZNkgMDg2SDEyQklDVzFiZnRlMVUwQ056NmV4UVFtSk56SGg).
    - Generate a token on the [Settings](https://www.discogs.com/settings/developers) page: click the *'Generate Token'* button.
    - Your token will be immediately available on the [Settings](https://www.discogs.com/settings/developers) page.

3. Do not share your API Key and token with anyone.
4. Save the API Key and the token to separate text files with no file extension.
5. Put the API Key and the token files in the **parent folder** of the folder from which the script will be executed. 
6. Make sure that **[MusicBrainz](https://musicbrainz.org/)** is accessible from your location (if not, use a VPN).
7. Run the Python script. 

## Script Description

Using the API, the script collects data from 3 data sources:

- *[MusicBrainz](https://musicbrainz.org/)* - an open music encyclopedia that contains music metadata ([API Docs](https://musicbrainz.org/doc/MusicBrainz_API));
- *[Discogs](https://www.discogs.com/)* - a database of information about audio recordings, including commercial releases, promotional releases, and bootleg or off-label releases ([API Docs](https://www.discogs.com/developers));
- *[Setlist.fm](https://www.setlist.fm/)* - a free wiki-like service to collect and share setlists ([API Docs](https://api.setlist.fm/docs/1.0/index.html)).

... and then prepares data for analysis and visualize them. 

All 3 sources can be freely edited by users, so some typos, missing data and contradictions are inevitable.

The logic behind the script:

1. Find artist and get its ID from MusicBrainz (API).
2. Use artist ID to get the list of IDs of *official studio albums* (Web Scraping + API).
3. Use the list of albums' IDs to get the corresponding tracklists from Discogs (API). 
4. Use artist ID to get setlists from Setlist.fm (API).
5. Clean, blend and prepare data for analysis (pandas, numpy, itertools, etc.).
6. Visualize data (plotly).

## Available Info

For now, the following information can be accessed:

1. General Data about Setlists.
2. *(Chart)* Events by Year.
3. *(Chart)* Events by Month.
4. *(Chart)* Events by Country on Map.
5. *(Chart)* Events by City on Map.
6. *(Chart)* Top 30 Played Songs.
7. *(Chart)* Top 30 Visited Countries.
8. *(Chart)* Top 30 Visited Cities.
9. *(Chart)* Shares of Album Songs in Setlists.
10. *(Chart)* Albums Played Over the Years.
11. *(Chart)* Shares of Albums Played Over the Years. 
12. *(Chart)* Events by Day of the Week.
13. *(Chart)* Setlists Size.
14. *(Chart)* Filled Setlists Size.
15. Never Played Album Songs.
16. Rarely Played Album Songs.
17. Top 15 Non-Album Songs Played. 
18. Top 5 First and Last Songs.  
19. Table Data for Charts.

## Examples

In the *'Visualizations'* folder, you can find the examples of data visualizations created by the script ('.html' files) for several music bands: Franz Ferdinand, Depeche Mode, Metallica, Cage The Elephant.

## To Be Continued...

Plans for the future: 

- Add new info about setlists;
- Fix bugs;
- Add Jupyter Notebook with detailed analysis of specific artist;
- Add Tableau Visualizations.

## Contacts

If you have any questions, bug reports or suggestions, please contact me at elana27.data@gmail.com.
