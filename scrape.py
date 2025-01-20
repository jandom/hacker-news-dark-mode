import requests
from bs4 import BeautifulSoup

HN_BASE = "https://news.ycombinator.com"
HN_TABLE_SELECTOR = "#hnmain > tr:nth-child(3) > td > table"

def scrape_hn_table():
    """
    Fetches the Hacker News front page and returns the <table> element 
    matching the given CSS selector.
    """
    url = "https://news.ycombinator.com/"
    resp = requests.get(url)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Grab the table matching your selector
    table = soup.select_one(HN_TABLE_SELECTOR)


    # Convert all <a> tags to absolute links
    for a_tag in table.find_all("a", href=True):
        href = a_tag["href"]
        # If it's not already absolute (starting with http), prepend HN_BASE
        if "?" in href:
            # .lstrip("/") ensures we don't accidentally create a double-slash
            a_tag["href"] = f"{HN_BASE}/{href.lstrip('/')}"    
    
    return table

def replace_table_in_index_html(index_path="index.html"):
    # 1) Scrape table from Hacker News
    new_table = scrape_hn_table()
    if not new_table:
        print("Could not find the HN table using the selector.")
        return

    # 2) Parse the local index.html
    with open(index_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    local_soup = BeautifulSoup(html_content, "html.parser")

    # 3) Find the existing table in your local file
    old_table = local_soup.select_one(HN_TABLE_SELECTOR)
    if not old_table:
        print("Could not find a matching table in local index.html.")
        return

    # 4) Replace the local table with the newly scraped table
    old_table.replace_with(new_table)

    # 5) Write the updated HTML back to index.html
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(local_soup.prettify())

if __name__ == "__main__":
    replace_table_in_index_html("index.html")