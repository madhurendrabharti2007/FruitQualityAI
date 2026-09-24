"""Seed the editable fruit guidance catalog."""
import json
from app.database import Fruit, FruitNotebook, SessionLocal, init_db

DATA = {
    "Apple": ("Rich in fiber for comfortable digestion.", "Vitamin C and polyphenols support everyday wellness.", "Discard moldy apples in sealed organic waste; do not compost visibly moldy pieces."),
    "Banana": ("A convenient source of potassium and carbohydrates.", "Vitamin B6 supports normal energy metabolism.", "Seal heavily spotted or leaking bananas before placing them in organic waste."),
    "Mango": ("Provides vitamins A and C for immune and skin support.", "Naturally sweet energy with helpful antioxidants.", "Keep spoiled mango away from edible food and dispose of it in sealed organic waste."),
    "Orange": ("A bright source of vitamin C and fluid.", "Citrus fiber supports a balanced diet.", "Bag soft or moldy oranges before disposal and wash the storage surface."),
    "Grapes": ("Contain water and fiber for a refreshing snack.", "Plant compounds such as anthocyanins add antioxidant variety.", "Remove spoiled grapes from the bunch, bag them, and discard the affected fruit."),
    "Tomato": ("Offers vitamin C and the antioxidant lycopene.", "Low-calorie and naturally hydrating.", "Do not taste moldy tomatoes; bag them and clean the container they touched."),
    "Papaya": ("Provides vitamin C, vitamin A, and dietary fiber.", "A naturally colorful addition to a varied diet.", "Wrap leaking or moldy papaya and place it in organic waste."),
}

NUTRITION_DATA = {
    "Apple": {
        "serving": "100 g (raw, with skin)",
        "calories": 52,
        "protein_g": 0.3,
        "carbohydrates_g": 14,
        "fiber_g": 2.4,
        "sugar_g": 10,
        "fat_g": 0.2,
        "key_vitamins": [
            {"name": "Vitamin C", "amount": "4.6 mg", "dv_percent": 5},
            {"name": "Vitamin K", "amount": "2.2 mcg", "dv_percent": 2},
            {"name": "Vitamin B6", "amount": "0.04 mg", "dv_percent": 2},
            {"name": "Vitamin A (RAE)", "amount": "3 mcg", "dv_percent": 0},
        ],
        "key_minerals": [
            {"name": "Potassium", "amount": "107 mg", "dv_percent": 2},
            {"name": "Magnesium", "amount": "5 mg", "dv_percent": 1},
            {"name": "Phosphorus", "amount": "11 mg", "dv_percent": 1},
            {"name": "Calcium", "amount": "6 mg", "dv_percent": 0},
        ],
    },
    "Banana": {
        "serving": "100 g (raw)",
        "calories": 89,
        "protein_g": 1.1,
        "carbohydrates_g": 23,
        "fiber_g": 2.6,
        "sugar_g": 12,
        "fat_g": 0.3,
        "key_vitamins": [
            {"name": "Vitamin B6", "amount": "0.37 mg", "dv_percent": 22},
            {"name": "Vitamin C", "amount": "8.7 mg", "dv_percent": 10},
            {"name": "Folate (B9)", "amount": "20 mcg", "dv_percent": 5},
            {"name": "Vitamin A (RAE)", "amount": "3 mcg", "dv_percent": 0},
        ],
        "key_minerals": [
            {"name": "Potassium", "amount": "358 mg", "dv_percent": 8},
            {"name": "Magnesium", "amount": "27 mg", "dv_percent": 6},
            {"name": "Phosphorus", "amount": "22 mg", "dv_percent": 2},
            {"name": "Manganese", "amount": "0.27 mg", "dv_percent": 12},
        ],
    },
    "Mango": {
        "serving": "100 g (raw)",
        "calories": 60,
        "protein_g": 0.8,
        "carbohydrates_g": 15,
        "fiber_g": 1.6,
        "sugar_g": 14,
        "fat_g": 0.4,
        "key_vitamins": [
            {"name": "Vitamin C", "amount": "36.4 mg", "dv_percent": 40},
            {"name": "Vitamin A (RAE)", "amount": "54 mcg", "dv_percent": 6},
            {"name": "Folate (B9)", "amount": "43 mcg", "dv_percent": 11},
            {"name": "Vitamin B6", "amount": "0.12 mg", "dv_percent": 7},
        ],
        "key_minerals": [
            {"name": "Potassium", "amount": "168 mg", "dv_percent": 4},
            {"name": "Copper", "amount": "0.11 mg", "dv_percent": 12},
            {"name": "Magnesium", "amount": "9 mg", "dv_percent": 2},
            {"name": "Phosphorus", "amount": "11 mg", "dv_percent": 2},
        ],
    },
    "Orange": {
        "serving": "100 g (raw)",
        "calories": 47,
        "protein_g": 0.9,
        "carbohydrates_g": 12,
        "fiber_g": 2.4,
        "sugar_g": 9,
        "fat_g": 0.1,
        "key_vitamins": [
            {"name": "Vitamin C", "amount": "53.2 mg", "dv_percent": 59},
            {"name": "Folate (B9)", "amount": "30 mcg", "dv_percent": 8},
            {"name": "Vitamin B1 (Thiamine)", "amount": "0.09 mg", "dv_percent": 7},
            {"name": "Vitamin A (RAE)", "amount": "11 mcg", "dv_percent": 1},
        ],
        "key_minerals": [
            {"name": "Potassium", "amount": "181 mg", "dv_percent": 4},
            {"name": "Calcium", "amount": "40 mg", "dv_percent": 3},
            {"name": "Magnesium", "amount": "10 mg", "dv_percent": 2},
            {"name": "Phosphorus", "amount": "14 mg", "dv_percent": 2},
        ],
    },
    "Grapes": {
        "serving": "100 g (raw, European type)",
        "calories": 69,
        "protein_g": 0.7,
        "carbohydrates_g": 18,
        "fiber_g": 0.9,
        "sugar_g": 16,
        "fat_g": 0.2,
        "key_vitamins": [
            {"name": "Vitamin K", "amount": "14.6 mcg", "dv_percent": 12},
            {"name": "Vitamin C", "amount": "3.2 mg", "dv_percent": 4},
            {"name": "Vitamin B6", "amount": "0.09 mg", "dv_percent": 5},
            {"name": "Vitamin B2 (Riboflavin)", "amount": "0.07 mg", "dv_percent": 5},
        ],
        "key_minerals": [
            {"name": "Potassium", "amount": "191 mg", "dv_percent": 4},
            {"name": "Copper", "amount": "0.09 mg", "dv_percent": 10},
            {"name": "Manganese", "amount": "0.07 mg", "dv_percent": 3},
            {"name": "Magnesium", "amount": "7 mg", "dv_percent": 2},
        ],
    },
    "Tomato": {
        "serving": "100 g (raw, red)",
        "calories": 18,
        "protein_g": 0.9,
        "carbohydrates_g": 3.9,
        "fiber_g": 1.2,
        "sugar_g": 2.6,
        "fat_g": 0.2,
        "key_vitamins": [
            {"name": "Vitamin C", "amount": "13.7 mg", "dv_percent": 15},
            {"name": "Vitamin A (RAE)", "amount": "42 mcg", "dv_percent": 5},
            {"name": "Vitamin K", "amount": "7.9 mcg", "dv_percent": 7},
            {"name": "Vitamin B9 (Folate)", "amount": "15 mcg", "dv_percent": 4},
        ],
        "key_minerals": [
            {"name": "Potassium", "amount": "237 mg", "dv_percent": 5},
            {"name": "Phosphorus", "amount": "24 mg", "dv_percent": 2},
            {"name": "Magnesium", "amount": "11 mg", "dv_percent": 3},
            {"name": "Copper", "amount": "0.04 mg", "dv_percent": 4},
        ],
    },
    "Papaya": {
        "serving": "100 g (raw)",
        "calories": 43,
        "protein_g": 0.5,
        "carbohydrates_g": 11,
        "fiber_g": 1.7,
        "sugar_g": 8,
        "fat_g": 0.3,
        "key_vitamins": [
            {"name": "Vitamin C", "amount": "60.9 mg", "dv_percent": 68},
            {"name": "Vitamin A (RAE)", "amount": "55 mcg", "dv_percent": 6},
            {"name": "Vitamin E", "amount": "0.3 mg", "dv_percent": 2},
            {"name": "Folate (B9)", "amount": "37 mcg", "dv_percent": 9},
        ],
        "key_minerals": [
            {"name": "Potassium", "amount": "182 mg", "dv_percent": 4},
            {"name": "Magnesium", "amount": "21 mg", "dv_percent": 5},
            {"name": "Calcium", "amount": "20 mg", "dv_percent": 2},
            {"name": "Phosphorus", "amount": "10 mg", "dv_percent": 1},
        ],
    },
}

NOTEBOOK_DATA = {
    "Apple": {"highlight": "Fiber-rich and easy to add to everyday meals.", "benefits": [{"title": "Supports digestion", "description": "The skin and flesh provide dietary fiber, including pectin."}, {"title": "Provides vitamin C", "description": "A medium apple contributes vitamin C and protective plant compounds."}], "good_combinations": [{"combo_with": "Peanut butter", "benefit": "Adds protein and fat to make a more filling snack; the fat also helps absorb apple's fat-soluble antioxidants."}, {"combo_with": "Oats", "benefit": "Combines fruit fiber with the beta-glucan fiber in oats for sustained energy and gut support."}, {"combo_with": "Almonds", "benefit": "Almond fat improves absorption of apple polyphenols; together they balance sweet taste with protein and fiber."}], "bad_combinations": [{"combo_with": "Alcohol", "risk": "There is no special detox effect; pairing either with a large meal may worsen digestive discomfort for some people."}], "overconsumption_risk": "Large amounts can add substantial carbohydrate and natural sugar, and the fiber may cause bloating in sensitive people.", "rotten_fruit_harms": [{"risk_title": "Foodborne illness", "description": "Moldy or leaking apples may carry microbes and should not be tasted."}, {"risk_title": "Mold spread", "description": "Soft fruits can have contamination below the visible spot, so cutting around mold is not reliable."}], "safe_disposal_tip": "Bag moldy or leaking apples and place them in organic waste; clean any surface they touched.", "storage_tip": "Refrigerate apples in a ventilated drawer and keep them away from produce that is sensitive to ethylene."},
    "Banana": {"highlight": "A convenient source of potassium and carbohydrate.", "benefits": [{"title": "Provides potassium", "description": "Potassium supports normal muscle, nerve, and fluid balance functions."}, {"title": "Convenient energy", "description": "Carbohydrate and vitamin B6 make bananas a practical addition to meals and snacks."}], "good_combinations": [{"combo_with": "Greek yogurt", "benefit": "Adds protein and calcium to the banana's carbohydrate; balanced macros for recovery or breakfast."}, {"combo_with": "Oats", "benefit": "Makes a fiber-rich breakfast with longer-lasting satiety; banana sweetness reduces need for added sugar."}, {"combo_with": "Peanut butter", "benefit": "Balances fast-acting carbs with protein and fat; ideal pre-exercise or portable snack."}], "bad_combinations": [{"combo_with": "Large amounts of added sugar", "risk": "A sweetened banana dessert can become high in total sugar; portion size matters."}], "overconsumption_risk": "Eating many bananas can add excess calories and carbohydrate; very large potassium intake is mainly a concern for people with kidney disease or certain medicines.", "rotten_fruit_harms": [{"risk_title": "Fermentation and spoilage", "description": "Leaking, foul-smelling, or moldy bananas can cause stomach upset and should be discarded."}, {"risk_title": "Mold exposure", "description": "Visible mold can spread through soft flesh and is not made safe by trimming a small area."}], "safe_disposal_tip": "Seal leaking or moldy bananas in a bag and discard them with organic waste.", "storage_tip": "Keep bananas at room temperature until ripe, then refrigerate them to slow further ripening; the peel may darken."},
    "Mango": {"highlight": "A colorful source of vitamins A and C.", "benefits": [{"title": "Supports vitamin intake", "description": "Mango supplies vitamin C and carotenoids, including provitamin A compounds."}, {"title": "Adds fiber", "description": "Its flesh contributes fiber and fluid to a varied diet."}], "good_combinations": [{"combo_with": "Black beans", "benefit": "The sweet fruit and beans create a flavorful meal with fiber and plant protein; vitamin C in mango boosts iron absorption from beans."}, {"combo_with": "Plain yogurt", "benefit": "Pairs mango carbohydrate with protein and calcium; the probiotics complement mango fiber for digestion."}, {"combo_with": "Coconut rice", "benefit": "Combines mango sweetness with rice carbs and coconut fat for a balanced, satisfying meal."}], "bad_combinations": [{"combo_with": "Alcohol", "risk": "Mango does not prevent alcohol effects, and the combination may worsen digestive symptoms for some people."}], "overconsumption_risk": "Mango is nutritious but naturally sweet; large portions can contribute significant carbohydrate and calories.", "rotten_fruit_harms": [{"risk_title": "Food poisoning", "description": "Moldy, slimy, or fermented-smelling mango may contain harmful microbes."}, {"risk_title": "Mold spread", "description": "Because mango is soft, discard the whole fruit when mold has entered the flesh."}], "safe_disposal_tip": "Wrap leaking or moldy mango, keep it away from ready-to-eat foods, and use organic waste where available.", "storage_tip": "Ripen mangoes at room temperature, then refrigerate ripe fruit and eat it within a few days."},
    "Orange": {"highlight": "Hydrating citrus with vitamin C and fiber.", "benefits": [{"title": "Provides vitamin C", "description": "Vitamin C supports normal immune function and helps the body absorb iron from plant foods."}, {"title": "Whole-fruit fiber", "description": "Eating the segments rather than only juice retains more of the fruit's fiber."}], "good_combinations": [{"combo_with": "Lentils or spinach", "benefit": "Vitamin C from orange can help significantly improve absorption of non-heme iron in legumes and leafy greens."}, {"combo_with": "Walnuts", "benefit": "Pairs refreshing fruit with unsaturated fat and texture; the fat aids absorption of citrus antioxidants."}, {"combo_with": "Dark chocolate (70%+)", "benefit": "Orange vitamin C enhances iron and polyphenol uptake; complementary flavors without added sugar."}], "bad_combinations": [{"combo_with": "Grapefruit medicines", "risk": "Orange is different from grapefruit, but people taking medicines should check their own medication guidance rather than assume all citrus behaves alike."}], "overconsumption_risk": "Large amounts of fruit or juice can add sugar and acidity; juice has less fiber and may affect teeth when sipped frequently.", "rotten_fruit_harms": [{"risk_title": "Mold exposure", "description": "Discard oranges with visible mold, leaking juice, or an off smell rather than tasting them."}, {"risk_title": "Foodborne illness", "description": "Damaged citrus can support microbial growth, especially after peeling."}], "safe_disposal_tip": "Bag moldy oranges and clean the fruit bowl or shelf before replacing fresh produce.", "storage_tip": "Store whole oranges in a cool, ventilated place or refrigerate them for longer keeping."},
    "Grapes": {"highlight": "A water-rich snack with fiber and plant compounds.", "benefits": [{"title": "Hydrating snack", "description": "Grapes contain substantial water and contribute carbohydrate for energy."}, {"title": "Plant compounds", "description": "Their skins contain polyphenols such as anthocyanins and resveratrol-related compounds."}], "good_combinations": [{"combo_with": "Cheese (feta or mozzarella)", "benefit": "Combines fruit carbohydrate with protein and fat for a balanced snack; salt in cheese balances grape sweetness."}, {"combo_with": "Almonds or walnuts", "benefit": "Adds protein, fiber, and unsaturated fat to grapes; nut fat increases absorption of grape skin antioxidants."}, {"combo_with": "Chicken salad", "benefit": "Adds natural sweetness and texture while grapes' acidity cuts through rich or creamy dressings."}], "bad_combinations": [{"combo_with": "Large amounts of juice", "risk": "Juicing removes much of the whole-fruit fiber and makes large portions easy to consume quickly."}], "overconsumption_risk": "Large portions can provide a lot of natural sugar and may cause digestive discomfort in some people.", "rotten_fruit_harms": [{"risk_title": "Mold spread", "description": "Mold can move between grapes in a bunch; discard affected soft grapes and inspect the rest carefully."}, {"risk_title": "Foodborne illness", "description": "Slimy or sour-smelling grapes should not be eaten."}], "safe_disposal_tip": "Remove and bag spoiled grapes, then wash the container before storing a new bunch.", "storage_tip": "Refrigerate unwashed grapes in a ventilated container and wash only what you are ready to eat."},
    "Tomato": {"highlight": "A versatile source of lycopene and vitamin C.", "benefits": [{"title": "Provides lycopene", "description": "Tomatoes contain lycopene, a carotenoid that is better absorbed with some dietary fat."}, {"title": "Low-energy, nutrient-rich", "description": "They add vitamin C, potassium, water, and flavor with relatively few calories."}], "good_combinations": [{"combo_with": "Olive oil", "benefit": "A little dietary fat can dramatically improve absorption of carotenoids such as lycopene and beta-carotene."}, {"combo_with": "Beans (chickpea, kidney)", "benefit": "Pairs complementary plant foods for fiber and protein; tomato vitamin C improves iron absorption from beans."}, {"combo_with": "Avocado", "benefit": "Avocado fat boosts lycopene and carotenoid absorption; creamy texture balances tomato acidity."}], "bad_combinations": [{"combo_with": "Very acidic meals", "risk": "Tomato can worsen reflux symptoms for some people; personal tolerance matters."}], "overconsumption_risk": "Large amounts may aggravate reflux or digestive discomfort in sensitive people, and tomato products can be high in sodium when processed.", "rotten_fruit_harms": [{"risk_title": "Mold exposure", "description": "Do not taste moldy tomatoes; their soft flesh can be contaminated below the surface."}, {"risk_title": "Foodborne illness", "description": "Leaking or foul-smelling tomatoes may harbor microbes and should be discarded."}], "safe_disposal_tip": "Bag moldy tomatoes and clean the container and shelf they touched.", "storage_tip": "Keep ripe tomatoes out of direct sun at room temperature for best flavor, or refrigerate briefly when fully ripe."},
    "Papaya": {"highlight": "A bright source of vitamin C, vitamin A, and fiber.", "benefits": [{"title": "Supports vitamin intake", "description": "Papaya is rich in vitamin C and provides carotenoids that the body can use to make vitamin A."}, {"title": "Contains fiber", "description": "Its soft flesh contributes dietary fiber and fluid."}], "good_combinations": [{"combo_with": "Lime juice", "benefit": "Adds flavor and extra vitamin C; the acid also slows browning of cut papaya."}, {"combo_with": "Pumpkin or chia seeds", "benefit": "Adds protein, minerals (magnesium, zinc), and omega-3 fats to papaya for a nutrient-dense snack."}, {"combo_with": "Greek yogurt", "benefit": "Protein and probiotics from yogurt complement papaya vitamin C and fiber for a balanced breakfast or snack."}], "bad_combinations": [{"combo_with": "Alcohol", "risk": "Papaya does not protect against alcohol effects, and the combination may irritate digestion for some people."}], "overconsumption_risk": "Large portions can add natural sugar and may cause loose stools or digestive discomfort in sensitive people.", "rotten_fruit_harms": [{"risk_title": "Foodborne illness", "description": "Discard papaya that is leaking, slimy, moldy, or smells fermented."}, {"risk_title": "Mold spread", "description": "Soft papaya can be contaminated beneath visible mold, so trimming is not a dependable solution."}], "safe_disposal_tip": "Wrap spoiled papaya, keep it away from other foods, and place it in organic waste.", "storage_tip": "Ripen papaya at room temperature, then refrigerate ripe cut pieces in a covered container."},
}

SHELF_LIFE = {
    "underripe": "3-6 days",
    "ripe": "2-4 days",
    "overripe": "1-2 days",
    "spoiled": "0 days",
}

def seed() -> None:
    init_db(); db = SessionLocal()
    for name, (benefit_a, benefit_b, disposal) in DATA.items():
        item = db.get(Fruit, name)
        if item is None:
            item = Fruit(name=name)
            db.add(item)
        item.benefits = json.dumps([benefit_a, benefit_b])
        item.harms = json.dumps(["Spoiled fruit can harbor microbes and may cause stomach upset.", "Visible mold can spread below the surface, so cutting around it is not a reliable fix."])
        item.disposal_tip = disposal
        item.sample_image = None
        notebook = db.get(FruitNotebook, name)
        if notebook is None:
            notebook = FruitNotebook(fruit_name=name)
            db.add(notebook)
        notebook_data = NOTEBOOK_DATA[name]
        notebook.highlight = notebook_data["highlight"]
        for field in ("benefits", "good_combinations", "bad_combinations", "rotten_fruit_harms"):
            setattr(notebook, field, json.dumps(notebook_data[field]))
        notebook.overconsumption_risk = notebook_data["overconsumption_risk"]
        notebook.safe_disposal_tip = notebook_data["safe_disposal_tip"]
        notebook.storage_tip = notebook_data["storage_tip"]
        notebook.shelf_life_days = json.dumps(SHELF_LIFE)
        notebook.nutrition_facts = json.dumps(NUTRITION_DATA.get(name, {}))
    db.commit(); db.close()

if __name__ == "__main__":
    seed()
