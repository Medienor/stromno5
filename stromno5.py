import requests
from datetime import datetime, date
import json
from weds import webflow_bearer_token

def get_electricity_api_url():
    today = date.today().strftime("%Y/%m-%d")
    return f"https://www.hvakosterstrommen.no/api/v1/prices/{today}_NO5.json"

def get_reservoir_data():
    url = "https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentOffentligDataSisteUke"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        for item in data:
            if item["omrType"] == "EL" and item["omrnr"] == 5:
                return item
    print(f"Failed to retrieve reservoir data. Status code: {response.status_code}")
    return None

webflow_url = "https://api.webflow.com/v2/collections/66a787627b197d409dd4ce8b/items/66a78844898fc08b7a056b4b/live"

def get_electricity_prices():
    url = get_electricity_api_url()
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        # Add VAT to all prices
        for item in data:
            item['NOK_per_kWh'] *= 1.25  # Add 25% VAT
        return sorted(data, key=lambda x: x['time_start'])
    else:
        print(f"Failed to retrieve electricity data. Status code: {response.status_code}")
        return None

def update_webflow_item(field_data):
    payload = {
        "isArchived": False,
        "isDraft": False,
        "fieldData": field_data
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {webflow_bearer_token}"
    }
    response = requests.patch(webflow_url, json=payload, headers=headers)
    if response.status_code == 200:
        print("Webflow item updated successfully")
    else:
        print(f"Failed to update Webflow item. Status code: {response.status_code}")
        print(response.text)

def main():
    prices = get_electricity_prices()
    reservoir_data = get_reservoir_data()
    
    if not prices or not reservoir_data:
        return

    field_data = {
        "name": "NO5",
        "slug": "no5s"
    }

    # Add today's date in the requested format
    today = date.today()
    field_data["dato"] = f"Strømprisen i dag, {today.strftime('%d.%m.%y')}"

    # Calculate average, highest, and lowest prices (now including VAT)
    nok_prices = [item['NOK_per_kWh'] for item in prices]
    avg_price = sum(nok_prices) / len(nok_prices)
    highest_price = max(nok_prices)
    lowest_price = min(nok_prices)

    # Add price fields (rounded to 2 decimal places)
    field_data["gjennomsnittsprisen"] = f"{avg_price:.2f}"
    field_data["hoyeste"] = f"{highest_price:.2f}"
    field_data["laveste"] = f"{lowest_price:.2f}"

    # Add reservoir data fields with updated formatting
    endring = reservoir_data['endring_fyllingsgrad']
    endring_formatted = f"+{endring * 100:.1f}" if endring >= 0 else f"{endring * 100:.1f}"
    field_data["endring-fyllingsgrad"] = endring_formatted

    # Set the indicator color based on the endring value
    field_data["endring-fyllingsgrad-indicator"] = "#d2ffd2" if endring >= 0 else "#ffb2b2"

    field_data["fyllingsgrad"] = f"{reservoir_data['fyllingsgrad'] * 100:.0f}%"
    field_data["fyllingsgrad-forrige-uke"] = f"{reservoir_data['fyllingsgrad_forrige_uke'] * 100:.0f}%"
    field_data["kapasitet"] = f"{reservoir_data['kapasitet_TWh']:.2f}"

    # Map prices to Webflow fields (now including VAT and rounded to 2 decimal places)
    for item in prices:
        time_start = datetime.fromisoformat(item['time_start'])
        field_key = f"{time_start.strftime('%H-%M')}---{(time_start.replace(hour=(time_start.hour + 1) % 24)).strftime('%H-%M')}"
        field_data[field_key] = f"{item['NOK_per_kWh']:.2f}"

    # Handle the last hour (23:00 - 00:00)
    if "23-00---00-00" not in field_data:
        field_data["23-00---00-00"] = field_data.get("23-00---24-00", "N/A")

    # Update Webflow item
    update_webflow_item(field_data)

    # Print the updated data
    print("Updated Webflow item with the following data:")
    print(json.dumps(field_data, indent=2))

if __name__ == "__main__":
    main()