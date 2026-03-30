"""
Seed script: 50 Houston furniture/goods/services listings for Phase 1.

Run with:
  docker-compose exec backend python db/seeds/houston_furniture.py

Or directly (with DB available):
  DATABASE_URL=postgresql://... python db/seeds/houston_furniture.py

Notes:
  - Embeddings are null on seed; run the embedding pipeline separately.
  - Listings cover diverse categories, price points, and Houston neighborhoods.
"""
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

LISTINGS = [
    # Mid-century modern furniture
    {
        "vertical": "goods", "category": "furniture",
        "title": "Mid-century modern sofa — walnut legs",
        "description": "Gorgeous mid-century modern sofa with solid walnut legs and mustard yellow upholstery. Like-new, barely used. Non-smoker home.",
        "price": 420.00, "location_raw": "Montrose, Houston, TX",
        "metadata": {"condition": "like new", "style": "mid-century modern", "material": "fabric", "pet_friendly": True},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Eames-style lounge chair + ottoman",
        "description": "Replica Eames lounge chair with matching ottoman. Dark walnut veneer, black leather. Excellent condition.",
        "price": 380.00, "location_raw": "Heights, Houston, TX",
        "metadata": {"condition": "excellent", "style": "mid-century modern", "material": "leather"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Danish teak credenza, 1960s",
        "description": "Authentic 1960s Danish teak credenza. Sliding doors, original hardware. Some patina adds character.",
        "price": 650.00, "location_raw": "Montrose, Houston, TX",
        "metadata": {"condition": "good", "style": "mid-century modern", "material": "teak"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Mid-century walnut dining table + 4 chairs",
        "description": "Walnut dining table with tapered legs, seats 6. Includes 4 matching chairs. Good condition, minor surface wear.",
        "price": 475.00, "location_raw": "Montrose, Houston, TX",
        "metadata": {"condition": "good", "style": "mid-century modern", "material": "walnut"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Sculptural accent chair — atomic age",
        "description": "Atomic-age accent chair with fiberglass shell and original chrome base. Great statement piece.",
        "price": 210.00, "location_raw": "Heights, Houston, TX",
        "metadata": {"condition": "good", "style": "mid-century modern", "material": "fiberglass"},
    },
    # Budget sofas
    {
        "vertical": "goods", "category": "furniture",
        "title": "Grey sectional sofa — great condition",
        "description": "Large L-shaped sectional, light grey microfiber. Pet-free, smoke-free home. 2 years old.",
        "price": 350.00, "location_raw": "Katy, TX",
        "metadata": {"condition": "great", "style": "contemporary", "material": "microfiber"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "IKEA Ektorp sofa — white slipcover",
        "description": "IKEA Ektorp 3-seat sofa with washable white slipcover. Well maintained. Pickup only.",
        "price": 150.00, "location_raw": "Sugar Land, TX",
        "metadata": {"condition": "good", "style": "contemporary", "brand": "ikea", "material": "cotton"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Blue velvet loveseat",
        "description": "Beautiful navy velvet loveseat with gold legs. Like-new condition. Perfect for apartment or home office.",
        "price": 280.00, "location_raw": "Midtown, Houston, TX",
        "metadata": {"condition": "like new", "style": "glam", "material": "velvet", "color": "navy"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Farmhouse style sofa — cream linen",
        "description": "Slip-covered farmhouse sofa in cream linen. Family-friendly, washable cover. Slight fading.",
        "price": 320.00, "location_raw": "The Woodlands, TX",
        "metadata": {"condition": "fair", "style": "farmhouse", "material": "linen", "color": "cream"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Leather sectional — dark brown",
        "description": "Genuine leather L-shaped sectional, dark chocolate brown. Recliner on one end. Some scuffs.",
        "price": 490.00, "location_raw": "Pearland, TX",
        "metadata": {"condition": "good", "style": "traditional", "material": "leather", "color": "brown"},
    },
    # Bedroom furniture
    {
        "vertical": "goods", "category": "furniture",
        "title": "Queen bed frame — solid oak",
        "description": "Solid oak platform queen bed frame with headboard. Clean, no mattress included.",
        "price": 200.00, "location_raw": "Montrose, Houston, TX",
        "metadata": {"condition": "excellent", "style": "contemporary", "material": "oak", "size": "queen"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Mid-century low-profile king bed",
        "description": "King platform bed with mid-century walnut veneer headboard. Extremely clean.",
        "price": 340.00, "location_raw": "Heights, Houston, TX",
        "metadata": {"condition": "excellent", "style": "mid-century modern", "material": "walnut veneer", "size": "king"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Dresser + mirror — 6-drawer solid wood",
        "description": "Six-drawer solid pine dresser with matching wall mirror. All drawers slide smoothly.",
        "price": 175.00, "location_raw": "Katy, TX",
        "metadata": {"condition": "good", "style": "traditional", "material": "pine"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Pair of matching nightstands",
        "description": "Matching pair of walnut-finish nightstands with drawer and shelf. Like-new.",
        "price": 120.00, "location_raw": "Midtown, Houston, TX",
        "metadata": {"condition": "like new", "style": "contemporary", "material": "walnut finish"},
    },
    # Tables
    {
        "vertical": "goods", "category": "furniture",
        "title": "Farmhouse dining table — seats 8",
        "description": "Large farmhouse dining table, reclaimed wood top with white base. Slight wear consistent with use.",
        "price": 395.00, "location_raw": "Cypress, TX",
        "metadata": {"condition": "good", "style": "farmhouse", "material": "reclaimed wood"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Glass dining table + 4 chairs",
        "description": "Round glass-top dining table (48 inch) with chrome base and 4 padded chairs. Very clean.",
        "price": 260.00, "location_raw": "Sugar Land, TX",
        "metadata": {"condition": "excellent", "style": "contemporary", "material": "glass/chrome"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Industrial coffee table — steel + wood",
        "description": "Industrial-style coffee table with steel pipe legs and solid wood top. Heavy-duty and sturdy.",
        "price": 150.00, "location_raw": "East End, Houston, TX",
        "metadata": {"condition": "excellent", "style": "industrial", "material": "steel and wood"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Marble-top side table",
        "description": "White marble-top end table with gold hairpin legs. Elegant. Small chip on underside not visible.",
        "price": 95.00, "location_raw": "Montrose, Houston, TX",
        "metadata": {"condition": "good", "style": "glam", "material": "marble"},
    },
    # Office furniture
    {
        "vertical": "goods", "category": "furniture",
        "title": "Standing desk — motorized height-adjustable",
        "description": "Flexispot motorized standing desk, 60x24 inch bamboo top. Works perfectly.",
        "price": 280.00, "location_raw": "Heights, Houston, TX",
        "metadata": {"condition": "excellent", "style": "modern", "type": "standing desk"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Ergonomic office chair — mesh back",
        "description": "Herman Miller-style ergonomic mesh chair. Full lumbar support, adjustable armrests.",
        "price": 145.00, "location_raw": "Greenway Plaza, Houston, TX",
        "metadata": {"condition": "good", "style": "office", "material": "mesh"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "L-shaped corner desk — home office",
        "description": "L-shaped desk, dark walnut finish, with built-in shelves. One side 60 inch, other 48 inch.",
        "price": 190.00, "location_raw": "Pearland, TX",
        "metadata": {"condition": "good", "style": "contemporary", "type": "corner desk"},
    },
    # Appliances
    {
        "vertical": "goods", "category": "appliance",
        "title": "Stainless steel refrigerator — French door",
        "description": "LG French door refrigerator, stainless steel, 25 cu ft. Ice maker and water dispenser.",
        "price": 620.00, "location_raw": "Sugar Land, TX",
        "metadata": {"condition": "excellent", "brand": "lg", "type": "refrigerator"},
    },
    {
        "vertical": "goods", "category": "appliance",
        "title": "Washer + dryer set — front load",
        "description": "Samsung front-load washer and dryer pair. White, energy efficient. 4 years old.",
        "price": 480.00, "location_raw": "Katy, TX",
        "metadata": {"condition": "good", "brand": "samsung", "type": "washer_dryer"},
    },
    {
        "vertical": "goods", "category": "appliance",
        "title": "Gas range — 5 burner stainless",
        "description": "GE 30-inch gas range, 5 burner, stainless steel. Convection oven.",
        "price": 370.00, "location_raw": "Midtown, Houston, TX",
        "metadata": {"condition": "good", "brand": "ge", "type": "range"},
    },
    {
        "vertical": "goods", "category": "appliance",
        "title": "Dishwasher — Bosch stainless",
        "description": "Bosch 500 series dishwasher, stainless steel tub, very quiet. 2 years old.",
        "price": 340.00, "location_raw": "The Woodlands, TX",
        "metadata": {"condition": "excellent", "brand": "bosch", "type": "dishwasher"},
    },
    # Electronics
    {
        "vertical": "goods", "category": "electronics",
        "title": "65-inch 4K OLED TV — LG",
        "description": "LG 65-inch OLED 4K TV (C1 series). Stunning picture quality. Original remote and stand.",
        "price": 900.00, "location_raw": "River Oaks, Houston, TX",
        "metadata": {"condition": "excellent", "brand": "lg", "type": "tv"},
    },
    {
        "vertical": "goods", "category": "electronics",
        "title": "MacBook Pro 14\" M1 Pro — like new",
        "description": "Apple MacBook Pro 14-inch, M1 Pro chip, 16GB RAM, 512GB SSD. Barely used.",
        "price": 1400.00, "location_raw": "Heights, Houston, TX",
        "metadata": {"condition": "like new", "brand": "apple", "type": "laptop"},
    },
    {
        "vertical": "goods", "category": "electronics",
        "title": "Sony PS5 console + 2 controllers",
        "description": "PlayStation 5 disc edition with 2 DualSense controllers. Excellent condition.",
        "price": 420.00, "location_raw": "Montrose, Houston, TX",
        "metadata": {"condition": "excellent", "brand": "sony", "type": "gaming console"},
    },
    {
        "vertical": "goods", "category": "electronics",
        "title": "iPad Pro 12.9\" M2 + Apple Pencil",
        "description": "iPad Pro 12.9-inch M2 chip, 256GB WiFi. Includes Apple Pencil 2nd gen.",
        "price": 750.00, "location_raw": "Greenway Plaza, Houston, TX",
        "metadata": {"condition": "good", "brand": "apple", "type": "tablet"},
    },
    # Outdoor furniture
    {
        "vertical": "goods", "category": "furniture",
        "title": "Patio sectional — all-weather wicker",
        "description": "6-piece outdoor sectional, all-weather wicker with beige cushions.",
        "price": 440.00, "location_raw": "Pearland, TX",
        "metadata": {"condition": "good", "style": "contemporary", "material": "wicker"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Teak outdoor dining set — 6 chairs",
        "description": "Solid teak outdoor dining table + 6 chairs. Weathered to silver-grey patina.",
        "price": 580.00, "location_raw": "River Oaks, Houston, TX",
        "metadata": {"condition": "good", "style": "coastal", "material": "teak"},
    },
    # Accent pieces
    {
        "vertical": "goods", "category": "furniture",
        "title": "Large area rug — 8x10 ft Persian-style",
        "description": "8x10 Persian-style wool rug, red and navy. Low traffic area, excellent condition.",
        "price": 260.00, "location_raw": "Montrose, Houston, TX",
        "metadata": {"condition": "excellent", "style": "traditional", "material": "wool"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Bookshelf — 6-tier industrial",
        "description": "Sturdy 6-tier industrial bookshelf with metal frame and wood shelves.",
        "price": 110.00, "location_raw": "East End, Houston, TX",
        "metadata": {"condition": "excellent", "style": "industrial", "material": "metal and wood"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Bar cart — gold and glass",
        "description": "Glamorous gold bar cart with two glass shelves. Perfect condition.",
        "price": 85.00, "location_raw": "Midtown, Houston, TX",
        "metadata": {"condition": "excellent", "style": "glam", "material": "glass and gold metal"},
    },
    # Bicycles
    {
        "vertical": "goods", "category": "bicycle",
        "title": "Trek hybrid bike — 7-speed",
        "description": "Trek FX3 hybrid bike, size medium, 7-speed. Barely ridden. Includes lock and lights.",
        "price": 320.00, "location_raw": "Heights, Houston, TX",
        "metadata": {"condition": "like new", "brand": "trek", "type": "hybrid"},
    },
    {
        "vertical": "goods", "category": "bicycle",
        "title": "Kids mountain bike — 24-inch wheels",
        "description": "Kids 24-inch mountain bike, 21-speed. Good condition, tuned up recently.",
        "price": 95.00, "location_raw": "Katy, TX",
        "metadata": {"condition": "good", "type": "mountain"},
    },
    # Services
    {
        "vertical": "services", "category": "home_repair",
        "title": "Handyman services — general repairs",
        "description": "Licensed handyman offering general home repairs: drywall, painting, fixture installation.",
        "price": 75.00, "location_raw": "Houston, TX",
        "metadata": {"type": "handyman", "rate_type": "hourly", "licensed": True},
    },
    {
        "vertical": "services", "category": "cleaning",
        "title": "House cleaning — deep clean",
        "description": "Professional deep cleaning service. 2-3 person team, eco-friendly products.",
        "price": 180.00, "location_raw": "Houston, TX",
        "metadata": {"type": "deep clean", "rate_type": "per_job", "eco_friendly": True},
    },
    {
        "vertical": "services", "category": "moving",
        "title": "Two-man moving crew — local Houston",
        "description": "Experienced 2-man moving crew with truck. Local Houston moves only.",
        "price": 120.00, "location_raw": "Houston, TX",
        "metadata": {"type": "moving", "rate_type": "hourly", "crew_size": 2},
    },
    # More furniture
    {
        "vertical": "goods", "category": "furniture",
        "title": "Rocking chair — solid maple",
        "description": "Classic solid maple rocking chair, natural finish. Excellent condition.",
        "price": 130.00, "location_raw": "The Woodlands, TX",
        "metadata": {"condition": "excellent", "style": "traditional", "material": "maple"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Velvet accent chair — emerald green",
        "description": "Plush emerald velvet accent chair with gold ring pull detail. Like-new.",
        "price": 165.00, "location_raw": "Midtown, Houston, TX",
        "metadata": {"condition": "like new", "style": "glam", "material": "velvet", "color": "emerald"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "King memory foam mattress — 10 inch",
        "description": "Zinus king memory foam mattress, 10 inch. Used 1 year, good condition.",
        "price": 180.00, "location_raw": "Pearland, TX",
        "metadata": {"condition": "good", "type": "mattress", "size": "king", "material": "memory foam"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Futon sofa bed — black metal frame",
        "description": "Futon converts to full-size bed. Black metal frame, dark grey mattress pad.",
        "price": 90.00, "location_raw": "East End, Houston, TX",
        "metadata": {"condition": "fair", "style": "contemporary", "color": "black", "type": "futon"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "TV console / entertainment unit",
        "description": "White lacquer TV console, 72 inches wide, 4 cabinet doors. Fits TVs up to 75 inch.",
        "price": 220.00, "location_raw": "Sugar Land, TX",
        "metadata": {"condition": "excellent", "style": "contemporary", "color": "white"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Chesterfield sofa — cognac leather",
        "description": "Genuine leather Chesterfield 3-seat sofa. Cognac/tan colour. Minor cracking on one armrest.",
        "price": 540.00, "location_raw": "River Oaks, Houston, TX",
        "metadata": {"condition": "good", "style": "traditional", "material": "leather", "color": "cognac"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Kids bedroom set — twin bed + dresser",
        "description": "White painted pine twin bed frame + matching 5-drawer dresser. From pet-free home.",
        "price": 195.00, "location_raw": "Cypress, TX",
        "metadata": {"condition": "excellent", "style": "traditional", "material": "pine", "color": "white"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Bar stools — set of 3, counter height",
        "description": "Set of 3 counter-height bar stools, black metal frame with round wood seat. Like-new.",
        "price": 150.00, "location_raw": "Heights, Houston, TX",
        "metadata": {"condition": "like new", "style": "industrial", "quantity": 3, "type": "bar stool"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Floating wall shelves — set of 5 walnut",
        "description": "Set of 5 solid walnut floating shelves, various lengths. Hardware included.",
        "price": 120.00, "location_raw": "Montrose, Houston, TX",
        "metadata": {"condition": "excellent", "style": "contemporary", "material": "walnut", "quantity": 5},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Plant stand — macramé and wood",
        "description": "Boho-style tiered plant stand with macramé details. Holds 3 plants. Excellent condition.",
        "price": 45.00, "location_raw": "Midtown, Houston, TX",
        "metadata": {"condition": "excellent", "style": "boho", "type": "plant stand"},
    },
    {
        "vertical": "goods", "category": "furniture",
        "title": "Dining bench — reclaimed wood",
        "description": "Reclaimed wood dining bench, 60 inches. Industrial iron legs. Heavy and solid.",
        "price": 105.00, "location_raw": "East End, Houston, TX",
        "metadata": {"condition": "excellent", "style": "industrial", "material": "reclaimed wood"},
    },
]


def run_seed(session):
    from app.db.models import Inventory

    added = 0
    for listing in LISTINGS:
        now = datetime.now(timezone.utc)
        item = Inventory(
            id=uuid.uuid4(),
            seller_id=None,
            vertical=listing["vertical"],
            category=listing["category"],
            title=listing["title"],
            description=listing["description"],
            metadata_json=listing.get("metadata", {}),
            price=listing["price"],
            price_negotiable=listing.get("price_negotiable", True),
            location_raw=listing.get("location_raw"),
            location_geom=None,
            embedding=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add(item)
        added += 1

    session.commit()
    print(f"Seeded {added} inventory listings.")


if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    DATABASE_URL = os.environ.get(
        "DATABASE_URL",
        "postgresql://tarpspace:tarpspace@localhost:5432/tarpspace",
    )
    engine = create_engine(DATABASE_URL)
    SessionFactory = sessionmaker(bind=engine)
    with SessionFactory() as session:
        run_seed(session)
