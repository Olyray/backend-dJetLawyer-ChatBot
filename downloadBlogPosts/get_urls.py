#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import json
import re

# Modified: Added import for re module

def get_links_starting_with(url, start_letter):
    # Fetch the webpage content
    response = requests.get(url)
    response.raise_for_status()

    # Parse the HTML content
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find all hyperlinks within the article tag
    article = soup.find('article')
    if not article:
        raise ValueError("No article tag found in the webpage")

    links = article.find_all('a')

    # Filter links that start with the specified letter
    filtered_links = []
    for link in links:
        # Modified: Added case-insensitive matching for the start letter
        if re.match(f'^{start_letter}', link.text.strip(), re.IGNORECASE):
            filtered_links.append(link.get('href'))

    return filtered_links

def save_urls_to_json(urls, filename):
    with open(filename, 'w') as f:
        json.dump(urls, f, indent=2)

def main():
    # Modified: Added input for URL and start letter
    url = "https://djetlawyer.com/index-to-the-laws-of-the-federation-of-nigeria/"
    start_letter = "U"

    try:
        filtered_urls = get_links_starting_with(url, start_letter)
        
        if not filtered_urls:
            print(f"No links starting with '{start_letter}' were found.")
        else:
            save_urls_to_json(filtered_urls, 'urls.json')
            print(f"Successfully saved {len(filtered_urls)} URLs to saved_urls.json")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()