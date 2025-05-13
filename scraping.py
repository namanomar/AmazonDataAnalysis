import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import random
import os
from datetime import datetime
from urllib.parse import urljoin

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://www.amazon.in/',
    'Upgrade-Insecure-Requests': '1',
    'Cache-Control': 'max-age=0'
}

def clean_text(text):
    if not text:
        return "N/A"
    return ' '.join(text.strip().split())

def extract_product_data(product, base_url="https://www.amazon.in"):
    try:
        title_element = product.find('h2')
        title = clean_text(title_element.text) if title_element else "N/A"
        link_element = title_element.find('a') if title_element else None
        if link_element and 'href' in link_element.attrs:
            product_url = urljoin(base_url, link_element['href'])
            product_url = re.sub(r'(/ref=.*|\?.*)', '', product_url)
            if '/dp/' not in product_url:
                dp_match = re.search(r'(/dp/[A-Z0-9]{10})', link_element['href'])
                if dp_match:
                    product_url = urljoin(base_url, dp_match.group(1))
        else:
            product_url = "N/A"
          # Get ASIN from product container and construct URL
        asin = product.get('data-asin')
        product_url = f"https://www.amazon.in/dp/{asin}" if asin else "N/A"

        brand = "N/A"
        brand_element = product.find('span', {'class': 'a-size-base-plus'})
        if brand_element:
            brand = clean_text(brand_element.text)
        
        
        rating = "N/A"
        rating_element = product.find('span', {'class': 'a-icon-alt'})
        if rating_element:
            rating_text = rating_element.text.strip()
            rating_match = re.search(r'(\d+\.\d+)', rating_text)
            if rating_match:
                rating = rating_match.group(1)
        if rating == "N/A":
            i_tag = product.find('i', {'class': 'a-icon-star-small'})
            if i_tag:
                class_value = i_tag.get('class', [])
                for cls in class_value:
                    if cls.startswith('a-star-small-'):
                        star_value = cls.replace('a-star-small-', '')
                        if star_value.isdigit():
                            rating = str(int(star_value) / 10)
                        elif '-' in star_value:
                            rating = star_value.replace('-', '.')
        reviews = "0"
        reviews_link = product.find('a', {'class': ['a-link-normal', 's-underline-text']})
        if reviews_link:
            reviews_text = reviews_link.text.strip()
            reviews_match = re.search(r'(\d+(?:,\d+)*)', reviews_text)
            if reviews_match:
                reviews = reviews_match.group(1).replace(',', '')
        if reviews == "0":
            reviews_span = product.find('span', {'class': 'a-size-base', 'dir': 'auto'})
            if reviews_span:
                reviews_text = reviews_span.text.strip()
                reviews_match = re.search(r'(\d+(?:,\d+)*)', reviews_text)
                if reviews_match:
                    reviews = reviews_match.group(1).replace(',', '')
        if reviews == "0":
            aria_labels = product.select('[aria-label]')
            for element in aria_labels:
                aria_text = element.get('aria-label', '')
                if 'ratings' in aria_text.lower() or 'reviews' in aria_text.lower():
                    reviews_match = re.search(r'(\d+(?:,\d+)*)', aria_text)
                    if reviews_match:
                        reviews = reviews_match.group(1).replace(',', '')
                        break
        price_element = product.find('span', {'class': 'a-price-whole'})
        price = f"₹{price_element.text}" if price_element else "N/A"
        img_element = product.find('img', {'class': 's-image'})
        image_url = img_element['src'] if img_element and 'src' in img_element.attrs else "N/A"
        bought_info = "N/A"
        bought_element = product.find('span', {'class': 'a-color-secondary'})
        if bought_element and "bought in past month" in bought_element.text:
            bought_info = clean_text(bought_element.text)
        if product.find('span', text=re.compile('Sponsored', re.IGNORECASE)):
            return {
                'Title': title,
                'Brand': brand,
                'Rating': rating,
                'Reviews': reviews,
                'Selling Price': price,
                'Product URL': product_url,
                'Image URL': image_url,
                
            }
        else:
            return 
    except Exception as e:
        print(f"Error extracting product data: {e}")
        return None

def scrape_amazon_products(search_term, max_pages=10):
    formatted_search = search_term.replace(' ', '+')
    products_data = []
    unique_products = set()
    for page_num in range(1, max_pages + 1):
        if page_num == 1:
            url = f"https://www.amazon.in/s?k={formatted_search}"
        else:
            url = f"https://www.amazon.in/s?k={formatted_search}&page={page_num}"
        print(f"\nScraping Amazon India for: {search_term} - Page {page_num}/{max_pages}")
        print(f"URL: {url}")
        try:
            if page_num > 1:
                sleep_time = random.uniform(3, 7)
                print(f"Waiting {sleep_time:.2f} seconds before requesting next page...")
                time.sleep(sleep_time)
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                no_results = soup.find('div', {'class': 'a-row', 'role': 'main'})
                if no_results and "No results for" in no_results.text:
                    print(f"Reached end of results. No more pages to scrape after page {page_num-1}.")
                    break
                all_products = soup.find_all('div', {'data-component-type': 's-search-result'})
                if not all_products:
                    print("No products found on this page. Amazon may have changed their HTML structure or blocked the request.")
                    if "Sorry" in soup.text and "robot" in soup.text:
                        print("CAPTCHA detected! Amazon has blocked the scraping attempt.")
                        break
                    continue
                print(f"Found {len(all_products)} products on page {page_num}")
                for product in all_products:
                    try:
                        product_data = extract_product_data(product)
                        if product_data:
                            product_id = re.search(r'/dp/([A-Z0-9]{10})', product_data['Product URL'])
                            product_key = product_id.group(1) if product_id else product_data['Title']
                            if product_key in unique_products:
                                print(f"Skipping duplicate product: {product_data['Title'][:50]}...")
                                continue
                            unique_products.add(product_key)
                            products_data.append(product_data)
                            print(f"Successfully scraped: {product_data['Title'][:50]}...")
                    except Exception as e:
                        print(f"Error extracting data from a product: {e}")
                        continue
                next_button = soup.find('a', {'class': 's-pagination-next'})
                if not next_button or 'a-disabled' in next_button.get('class', []):
                    print(f"No more pages available after page {page_num}.")
                    break
            else:
                print(f"Failed to retrieve page {page_num}. Status code: {response.status_code}")
                break
        except Exception as e:
            print(f"An error occurred while scraping page {page_num}: {e}")
            break
    print(f"\nCompleted scraping {page_num} pages.")
    print(f"Total products collected: {len(products_data)}")
    df = pd.DataFrame(products_data)
    return df

def extract_product_details(product_url):
    try:
        sleep_time = random.uniform(2, 5)
        print(f"Waiting {sleep_time:.2f} seconds before requesting product page...")
        time.sleep(sleep_time)
        response = requests.get(product_url, headers=headers)
        if response.status_code != 200:
            print(f"Failed to retrieve product page. Status code: {response.status_code}")
            return {}
        soup = BeautifulSoup(response.content, 'html.parser')
        details = {}
        title_element = soup.find('span', {'id': 'productTitle'})
        # details['Full Title'] = clean_text(title_element.text) if title_element else "N/A"
        brand = "Unknown"
        product_details = soup.find('table', {'id': 'productDetails_detailBullets_sections1'})
        if product_details:
            brand_row = product_details.find('th', string=re.compile('Brand', re.IGNORECASE))
            if brand_row and brand_row.find_next('td'):
                brand = clean_text(brand_row.find_next('td').text)
        if brand == "Unknown":
            product_info = soup.find('div', {'id': 'productDetails_techSpec_section_1'})
            if product_info:
                brand_row = product_info.find('th', string=re.compile('Brand', re.IGNORECASE))
                if brand_row and brand_row.find_next('td'):
                    brand = clean_text(brand_row.find_next('td').text)
        if brand == "Unknown":
            byline = soup.find('a', {'id': 'bylineInfo'})
            if byline:
                brand_text = byline.text.strip()
                if 'Brand:' in brand_text:
                    brand = clean_text(brand_text.split('Brand:')[1])
                elif 'Visit the' in brand_text:
                    brand = clean_text(brand_text.replace('Visit the', '').replace('Store', ''))
        details['Brand'] = brand
        rating_element = soup.find('span', {'id': 'acrPopover'})
        if rating_element:
            rating_text = rating_element.get('title', '')
            rating_match = re.search(r'(\d+\.\d+)', rating_text)
            details['Rating'] = rating_match.group(1) if rating_match else "N/A"
        else:
            details['Rating'] = "N/A"
        reviews_element = soup.find('span', {'id': 'acrCustomerReviewText'})
        if reviews_element:
            reviews_text = reviews_element.text.strip()
            reviews_match = re.search(r'(\d+(?:,\d+)*)', reviews_text)
            details['Reviews'] = reviews_match.group(1).replace(',', '') if reviews_match else "0"
        else:
            details['Reviews'] = "0"
        
        
        return details
    except Exception as e:
        print(f"Error extracting product details: {e}")
        return {}

def main():
    search_term = "soft toys"
    # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = f"amazon_scrape_results"
    os.makedirs(results_dir, exist_ok=True)
    max_pages = 20
    print(f"Starting to scrape Amazon India for '{search_term}' across up to {max_pages} pages...")
    df = scrape_amazon_products(search_term, max_pages)
    if not df.empty:
        raw_output_file = os.path.join(results_dir, f"amazon_india_{search_term.replace(' ', '_')}_raw.csv")
        df.to_csv(raw_output_file, index=False)
        print(f"Raw data saved to {raw_output_file}")
        print("\nExtracting detailed information for selected products...")
        detailed_products = []
        limit = len(df)
        for i, row in df.head(limit).iterrows():
            if row['Product URL'] != 'N/A':
                print(f"\nProcessing product {i+1}/{limit}: {row['Title'][:50]}...")
                details = extract_product_details(row['Product URL'])
                combined_info = {**row.to_dict(), **details}
                detailed_products.append(combined_info)
                print(f"Successfully extracted detailed information for product {i+1}")
        if detailed_products:
            df_detailed = pd.DataFrame(detailed_products)
            detailed_output_file = os.path.join(results_dir, f"amazon_india_{search_term.replace(' ', '_')}_detailed.csv")
            df_detailed.to_csv(detailed_output_file, index=False)
            print(f"\nDetailed data saved to {detailed_output_file}")
    else:
        print("No data was scraped.")

if __name__ == "__main__":
    main()
