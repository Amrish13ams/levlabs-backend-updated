import requests
import sys

BASE_URL = "http://localhost:5000"

def create_data():
    print("Seeding data...")

    # 1. Create Fabric Group
    print("Creating Fabric Group...")
    fg = requests.post(f"{BASE_URL}/fabric-groups", json={
        "name": "Suit Fabrics",
        "description": "Premium Wool and Linen collection"
    }).json()
    fg_id = fg['id']

    # 2. Add Fabrics
    print("Adding Fabrics...")
    requests.post(f"{BASE_URL}/fabrics", json={"name": "Blue Wool", "fabric_group_id": fg_id, "image_urls": "https://images.suitsupply.com/blue_wool.jpg"})
    requests.post(f"{BASE_URL}/fabrics", json={"name": "Grey Linen", "fabric_group_id": fg_id, "image_urls": "https://images.suitsupply.com/grey_linen.jpg"})

    # 3. Create Root Product (Suit Jacket)
    print("Creating Root Product (Suit Jacket)...")
    suit = requests.post(f"{BASE_URL}/products", json={
        "name": "Suit Jacket",
        "fabric_group_id": fg_id,
        "meta_type": "root"
    }).json()
    suit_id = suit['id']

    # 4. Create Category (Lapel)
    print("Creating Category (Lapel)...")
    lapel = requests.post(f"{BASE_URL}/products", json={
        "name": "Lapel",
        "parent_id": suit_id,
        "attributes_list": ["width", "Buttonhole"],
        "meta_type": "category"
    }).json()
    lapel_id = lapel['id']

    # 5. Create Style (Notch)
    print("Creating Style (Notch)...")
    notch = requests.post(f"{BASE_URL}/products", json={
        "name": "Notch",
        "parent_id": lapel_id,
        "description": "The most standard and versatile lapel works well for any occasion.",
        "image_urls": "https://images.suitsupply.com/notch.jpg",
        "meta_type": "product"
    }).json()
    notch_id = notch['id']

    # 6. Create Attribute Options for Notch
    print("Adding Options to Notch...")
    # Width
    requests.post(f"{BASE_URL}/products", json={"name": "Narrow", "parent_id": notch_id, "attribute_name": "width", "price": 0, "meta_type": "attribute"})
    requests.post(f"{BASE_URL}/products", json={"name": "Standard", "parent_id": notch_id, "attribute_name": "width", "price": 0, "meta_type": "attribute"})
    # Buttonhole
    requests.post(f"{BASE_URL}/products", json={"name": "Traditional", "parent_id": notch_id, "attribute_name": "Buttonhole", "price": 0, "meta_type": "attribute"})
    requests.post(f"{BASE_URL}/products", json={"name": "Handmade", "parent_id": notch_id, "attribute_name": "Buttonhole", "price": 20, "meta_type": "attribute"})

    # 7. Create Category (Pockets)
    print("Creating Category (Pockets)...")
    pockets = requests.post(f"{BASE_URL}/products", json={
        "name": "Pockets",
        "parent_id": suit_id,
        "meta_type": "category"
    }).json()
    pockets_id = pockets['id']

    # 8. Create Styles (Pockets)
    print("Adding Pocket Styles...")
    requests.post(f"{BASE_URL}/products", json={"name": "Flap Pockets", "parent_id": pockets_id, "meta_type": "product"})
    requests.post(f"{BASE_URL}/products", json={"name": "Patch Pockets", "parent_id": pockets_id, "meta_type": "product"})

    print("Done! Data structure created.")

if __name__ == "__main__":
    create_data()