"""Crawl matchday data for all leagues."""

import re
import urllib3
import certifi
import pandas as pd

from bs4 import BeautifulSoup
from unidecode import unidecode
from bld.project_paths import project_paths_join as ppj


def get_soup_obj(url):
    """
    Given an URL this function returns the soup object, i.e., it gets
    the page request and pulls the data out of HTML code needed to
    start the actual web scraping process.
    """
    http = urllib3.PoolManager(
        cert_reqs='CERT_REQUIRED',
        ca_certs=certifi.where())

    page_request = http.request("GET", url)
    soup = BeautifulSoup(page_request.data, 'lxml')
    
    return soup


def get_district_list(region, main_url, matchday_dict):
    """
    Given a region name and the fupa URL this function finds all
    districts within the region and constructs the corresponding URL. 
    Region name and URL are stored in a matchday dict, that later is 
    appended to a dataframe containing all leagues across all regions.
    """

    # Get soup object from predefined regions.
    region_url = main_url + "/" + region
    region_soup = get_soup_obj(region_url)

    # Store region name and corresponding url in matchday dictionary.
    matchday_dict['region'] = unidecode(region)
    matchday_dict['region_url'] = region_url

    # Find district object from region soup object, construct url for
    # each district and store those urls in a list.
    districts_soup = region_soup.find('td', {'class': 'kreise_select'}).div
    districts_url_list = [main_url + a['href']
                          for a in districts_soup.find_all('a', href=True) if a.text]
    districts_url_list = [x for x in districts_url_list if not "profi" in x]
    # Remove region_url, which is contained in district soup object by default.
    districts_url_list.remove(region_url)

    return districts_url_list


def get_league_list(district_url, matchday_dict, main_url):
    """
    Given a district level URL this function returns a list of the 
    leagues URLs within the district.
    """

    district_soup = get_soup_obj(district_url)
    district = district_soup.find(
        'td', {'class': 'kreise_select'}).div.a.span.text
    district = re.sub('\s|-', '_', district).lower()

    matchday_dict['district'] = unidecode(district)
    matchday_dict['district_url'] = district_url

    leagues_soup = district_soup.find(
        'td', {'class': 'liga-select first-selected'}).div
    leagues_url_list = [main_url + a['href']
                        for a in leagues_soup.find_all('a', href=True) if a.text]
    # At this stage I exclude pokal championships, since the structure is
    # quite different from normal leagues.
    exclsn_strngs = ['pokal', 'hallen', 'cup']
    leagues_url_list = [x for x in leagues_url_list if not any(
        strng in x for strng in exclsn_strngs)]

    return leagues_url_list


def get_seaons_list(league_url, matchday_dict):
    """
    Given a league url this function returns a list, containing the
    URL of all past seasons of this league. League name and url are
    stored in a matchday dictionary.
    """

    # Get soup object for given league url.
    league_soup = get_soup_obj(league_url)

    # League name to create unique ID in the end.
    league_name = league_soup.find(
        'div', {'class': 'content_team_header'}).h1.text
    league_name = re.sub('\s|-', '_', re.sub(
        ",", "", league_name)).lower()

    # Write league and corresponding url in matchday dictionary.
    matchday_dict['league'] = unidecode(league_name)
    matchday_dict['league_url'] = league_url

    # Extract all previous seasons.
    seasons_list = league_soup.find(
        'table', {'class': 'liga_tabelle_archiv'})
    seasons_list = seasons_list.findAll('a')

    return seasons_list[0:5]


def get_matchday_url(season, matchday_dict, matchday_df):
    """
    Given a season URL this function extracts the corresponding
    matchday URL, from which the actual scraping process starts. 
    Further, it saves information about the season in the matchday
    dictionary, while also constructing an unique ID for each season.
    """

    # Maybe just do this in the end for the ID string?
    season_name = re.sub('/', '_', season.text)

    # For the current season the way to access the matchday page is
    # slightly different from the one to access past seasons.
    if 'html' in season['href']:  # Past seasons.
        mtchdy_season_url = season['href'].replace(
            '.html', '/spielplan.html')
        matchday_dict['current_season'] = 0
    else:  # Current season.
        mtchdy_season_url = season['href'] + '/spielplan'
        matchday_dict['current_season'] = 1

    # Store further information about league in matchday dictionary.
    matchday_dict['done'] = 0
    matchday_dict['season'] = unidecode(season_name)
    matchday_dict['mtchdy_url'] = mtchdy_season_url

    # Construct unique ID for each season by combining information from
    # all four stages of scraping process.
    matchday_dict['mtchday_id'] = '_'.join(
        [
            matchday_dict['region'],
            matchday_dict['district'],
            matchday_dict['league'],
            matchday_dict['season']
        ]
    )

    # Append dictionary to matchday dataframe.
    matchday_df = matchday_df.append(
        matchday_dict, ignore_index=True)

    return matchday_df


def main():
    # Main URL to start from.
    main_url = 'https://www.fupa.net'
    # Regions to scrap.
    regions = ['mittelrhein']
    # regions = ['mittelrhein', 'niederrhein', 'ruhrgebiet', 'westrhein']

    # Intitalize dictionary and pandas dataframe to store league data.
    matchday_dict = dict()
    matchday_df = pd.DataFrame()

    # Loop through all predefined regions to get district districs within each
    # region.
    for region in regions:
        district_url_list = get_district_list(region, main_url, matchday_dict)

        # Loop through districts to get leagues within each district.
        for district_url in district_url_list:
            leagues_url_list = get_league_list(
                district_url, matchday_dict, main_url)

            # Loop through each single league to get list of all past seasons
            # within a league.
            for league_url in leagues_url_list:
                seasons_list = get_seaons_list(league_url, matchday_dict)

                # Get matchday url for all seasons within a league, from which
                # to start scraping.
                for season in seasons_list:
                    matchday_df = get_matchday_url(
                        season, matchday_dict, matchday_df)

    # Save matchday dataframe as .csv file.
    matchday_df.to_csv(ppj('OUT_DATA_FOOTBALL', 'matchday_data.csv'))


if __name__ == '__main__':
    main()
