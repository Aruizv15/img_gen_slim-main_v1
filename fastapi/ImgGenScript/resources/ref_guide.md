# **Style System Reference Guide**  
*Tag-Based Visual Coherence for Donor Image Generation*

---

## 1. **Style Tags Overview**

All visual elements in the system are controlled via **semantic tags**. These tags are grouped into **categories** that define compatibility and coherence.

| Category | Tags | Description |
|--------|------|-----------|
| **Color Clarity / Luminosity** | `clarity_light`, `clarity_neutral`, `clarity_dark` | Brightness level of colors |
| **Color Intensity / Saturation** | `saturation_low`, `saturation_medium`, `saturation_high`, `saturation_extreme` | Vibrancy from muted to neon |
| **Color Hue** | `hue_warm`, `hue_cool`, `hue_neutral` | Temperature direction |
| **Color Family** | `family_red`, `family_green`, `family_blue`, `family_cyan`, `family_yellow`, `family_magenta`, `family_orange`, `family_brown`, `family_white`, `family_black` | Base color group |
| **Makeup Intensity** | `makeup_intensity_none`, `makeup_intensity_light`, `makeup_intensity_medium`, `makeup_intensity_heavy` | Level of makeup application |
| **Temperature** | `temp_hot`, `temp_neutral`, `temp_cold` | Weather-appropriate clothing |
| **Light Temperature** | `light_temp_warm`, `light_temp_neutral`, `light_temp_cool` | Lighting color tone |
| **Style** | `style_casual`, `style_formal`, `style_soft`, `style_sporty`, `style_chic`, `style_vintage`, `style_minimalist`, `style_street`, `style_boho`, `style_edgy`, `style_academic`, `style_preppy`, `style_athleisure`, `style_glam`, `style_playful` | Aesthetic direction |
| **Emotion** | `emotion_happy`, `emotion_calm`, `emotion_confident`, `emotion_playful`, `emotion_thoughtful`, `emotion_neutral`, `emotion_intense` | Facial expression & mood |
| **Garment** | `garment_tshirt`, `garment_blouse`, `garment_top`, `garment_tank_top`, `garment_sweater`, `garment_hoodie`, `garment_vest`, `garment_cardigan`, `garment_jacket`, `garment_blazer`, `garment_coat`, `garment_dress`, `garment_jumpsuit`, `garment_skirt`, `garment_shorts`, `garment_jeans`, `garment_pants`, `garment_overalls` | Garment type |
| **Shoes** | `shoe_sneakers`, `shoe_sandals`, `shoe_heels`, `shoe_flats`, `shoe_boots`, `shoe_espadrilles`, `shoe_platforms`, `shoe_clogs` | Footwear |
| **Hair Type** | `hair_type_straight`, `hair_type_wavy`, `hair_type_curly`, `hair_type_coily` | Hair texture |
| **Hair Length** | `hair_length_short`, `hair_length_medium`, `hair_length_long` | Hair length |
| **Pose Type** | `pose_standing`, `pose_sitting`, `pose_leaning`, `pose_walking` | Body position |
| **Environment** | `env_studio`, `env_indoor`, `env_outdoor`, `env_urban`, `env_natural` | Scene setting |

> **Note**: Tags are **not mutually exclusive**.

### Garment
This category specifies the **type of garment** worn by the subject, focusing on the main clothing piece(s) to generate a complete outfit. It includes all essential apparel, from tops and outerwear to bottoms and one-piece garments. The table below provides a detailed breakdown of each specific garment tag and explaining its scope

| Tag | Description |
| :--- | :--- |
| **garment_tshirt** | Basic cotton or knit short/long-sleeve tops (T-shirt, Cropped t-shirt). |
| **garment_blouse** | Loose, fluid, or detailed upper garments (Loose blouse, Linen blouse, Off-the-shoulder blouse). |
| **garment_top** | Fitted, short, or lingerie-style upper garments (Crop top, Fitted top, Camisole top, Silk camisole). |
| **garment_tank_top** | Sleeveless tops or shirts (Tank top, Silk tank top). |
| **garment_sweater** | Thick or warm knit garments (Jerseys, Turtleneck sweater). |
| **garment_hoodie** | Sweatshirts with a hood, either zip-up or pullover. |
| **garment_vest** | Vests, whether knit, tailored, or of other material, worn as a layer or main garment. |
| **garment_cardigan** | Open sweater worn as a main garment or light layer (Cardigan, Long knit cardigan). |
| **garment_jacket** | Light or medium-weight jackets, including leather or overshirts (Denim jacket, Leather jacket, Flannel overshirt). |
| **garment_blazer** | Structured dress jackets, often part of a suit or used for a formal/chic look (Blazer). |
| **garment_coat** | Long and heavy coats (Trench coat). |
| **garment_dress** | Any type of one-piece dress (Sweater dress, Flowy dress, Shirt dress, Slip dress). |
| **garment_jumpsuit** | Full-body jumpsuits or overalls (Short/Long jumpsuit). |
| **garment_skirt** | Skirts (Denim midi skirt, Pencil skirt, Pleated midi skirt, Knit midi skirt). |
| **garment_shorts** | Short pants (Denim shorts, Tailored shorts, Paper bag waist shorts). |
| **garment_jeans** | Denim pants (Fitted, Skinny, Boyfriend, Wide-leg). |
| **garment_pants** | All non-denim trousers (Dress pants, Corduroy pants, Culottes, Cropped trousers, Leggings). |
| **garment_overalls** | One-piece garments or bib-and-brace overalls, usually made of denim or other casual materials. |

### Shoes
This category defines the specific **type of footwear** for the subject. The table below provides a detailed breakdown of each specific shoe tag and explaining its scope

| Tag | Description |
| :--- | :--- |
| **shoe_sneakers** | Athletic or casual footwear (White sneakers, Platform sneakers, Vintage sneakers, Chunky sneakers). |
| **shoe_sandals** | Open summer footwear (Strappy sandals, Flat sandals, Heeled sandals, Platform sandals). |
| **shoe_heels** | High-heeled, elegant, or cocktail footwear (Heels, Low heels, Block heels). |
| **shoe_flats** | Closed or semi-closed flat footwear (Ballet flats, Loafers, Mules). |
| **shoe_boots** | Footwear covering the ankle or higher (Ankle boots, Knee-high boots, Thigh-high boots). |
| **shoe_espadrilles** | Footwear with esparto or jute soles (Generally espadrilles or summer platforms). |
| **shoe_platforms** | Footwear with a thick, uniformly raised sole, including sneakers, sandals, or boots. |
| **shoe_clogs** | Clogs, footwear characterized by a thick sole, often made of wood, and a closed upper. |

---

## 2. **Style Elements & Their Tags**

Each visual component is defined in its own JSON file under `backend/cfg/styles_data/`. Below is the **tag structure** for each.

---

### **`outfits_portrait.json`**
| Field | Type | Required | Tags Used |
|------|------|---------|----------|
| `value` | string | Yes | Upper body only |
| `tags.temperature` | array | Yes | `temp_*` |
| `tags.environment` | array | Yes | `env_*` |
| `tags.color_*` | array | Yes | `clarity_*`, `saturation_*`, `hue_*`, `family_*` |
| `tags.makeup_intensity` | array | Yes | `makeup_intensity_*` |
| `tags.items` | array | Yes | `garment_*` |
| `style` | array | Yes | `style_*` |

**Example**:
```json
{
  "value": "{outfit_color} flowy blouse",
  "tags": {
    "temperature": ["temp_hot", "temp_neutral"],
    "environment": ["env_studio", "env_indoor", "env_natural", "env_outdoor"],
    "color_clarity": ["clarity_light", "clarity_neutral"],
    "color_saturation": ["saturation_low", "saturation_medium"],
    "color_hue": ["hue_cool", "hue_warm"],
    "color_family": ["family_red", "family_green", "family_blue", "family_yellow", "family_magenta", "family_orange", "family_brown", "family_white"],
    "makeup_intensity": ["makeup_intensity_none", "makeup_intensity_light"],
    "garment": ["garment_blouse"]
  },
  "style": ["style_soft", "style_boho"]
}
```

---

### **`outfits_fullbody.json`**
| Field | Type | Required | Tags Used |
|------|------|---------|----------|
| `value` | string | Yes | Uses `{outfit_color}` placeholder |
| `tags.temperature` | array | Yes | `temp_*` |
| `tags.environment` | array | Yes | `env_*` |
| `tags.color_*` | array | Yes | `clarity_*`, `saturation_*`, `hue_*`, `family_*` |
| `tags.makeup_intensity` | array | Yes | `makeup_intensity_*` |
| `tags.garment` | array | Yes | `garment_*` |
| `tags.shoes` | array | Yes | `shoe_*` |
| `style` | array | Yes | `style_*` |

**Example**:
```json
{
  "value": "{outfit_color} flowy midi dress with flat sandals",
  "tags": {
    "temperature": ["temp_hot", "temp_neutral"],
    "environment": ["env_outdoor", "env_natural"],
    "garment": ["garment_dress"],
    "shoes": ["shoe_sandals"]
  },
  "style": ["style_boho", "style_soft"]
}
```

---

### **`outfit_colors.json`**
| Field | Type | Required | Tags Used |
|------|------|---------|----------|
| `value` | string | Yes | — |
| `tags.color_clarity` | array | Yes | `clarity_*` |
| `tags.color_saturation` | array | Yes | `saturation_*` |
| `tags.color_hue` | array | Yes | `hue_*` |
| `tags.color_family` | array | Yes | `family_*` |
| `style` | array | Yes | `style_*` |

**Example**:
```json
{
  "value": "Sage Green",
  "tags": {
    "color_clarity": ["clarity_light"],
    "color_saturation": ["saturation_low"],
    "color_hue": ["hue_cool"],
    "color_family": ["family_green"]
  },
  "style": ["style_soft", "style_boho", "style_vintage", "style_minimalist"]
}
```

---

### **`hairstyles.json`**
| Field | Type | Required | Tags Used |
|------|------|---------|----------|
| `value` | string | Yes | — |
| `tags.hair_type` | array | Yes | `hair_type_*` |
| `tags.hair_length` | array | Yes | `hair_length_*` |
| `style` | array | Yes | `style_*` |

**Example**:
```json
{
  "value": "French Braid",
  "tags": {
    "hair_type": ["hair_type_straight", "hair_type_wavy"],
    "hair_length": ["hair_length_long"]
  },
  "style": ["style_soft", "style_preppy", "style_academic"]
}
```

---

### **`makeups.json`**
| Field | Type | Required | Tags Used |
|------|------|---------|----------|
| `value` | string | Yes | — |
| `tags.makeup_intensity` | array | Yes | `makeup_intensity_*` |
| `style` | array | Yes | `style_*` |

**Example**:
```json
{
  "value": "Smokey Eye",
  "tags": { "makeup_intensity": ["makeup_intensity_heavy"] },
  "style": ["style_edgy", "style_glam", "style_street", "style_chic"]
}
```

---

### **`expressions.json`**
| Field | Type | Required | Tags Used |
|------|------|---------|----------|
| `value` | string | Yes | — |
| `tags.emotion` | array | Yes | `emotion_*` |
| `style` | array | Yes | `style_*` |

**Example**:
```json
{
  "value": "soft smile",
  "tags": {
    "emotion": ["emotion_happy", "emotion_calm"]
  },
  "style": ["style_soft", "style_chic", "style_casual", "style_formal", "style_academic"]
}
```

---

### **`poses.json`**
| Field | Type | Required | Tags Used |
|------|------|---------|----------|
| `value` | string | Yes | — |
| `tags.type` | array | Yes | `pose_*` |
| `tags.emotion` | array | Yes | `emotion_*` |
| `style` | array | Yes | `style_*` |

**Example**:
```json
{
  "value": "hands on hips, looking confidently at the camera",
  "tags": {
    "type": ["pose_standing"],
    "emotion": ["emotion_confident"]
  },
  "style": ["style_sporty", "style_athleisure", "style_casual", "style_street"]
}
```

---

### **`locations.json`**
| Field | Type | Required | Tags Used |
|------|------|---------|----------|
| `value` | string | Yes | Full scene description |
| `tags.temperature` | array | Yes | `temp_*` |
| `tags.environment` | array | Yes | `env_*` |
| `style` | array | Yes | `style_*` |

**Example**:
```json
{
  "value": "in a professional photo studio, clean uncluttered setup, no equipment visible, seamless white paper backdrop",
  "tags": {
    "temperature": ["temp_hot", "temp_neutral", "temp_cold"],
    "environment": ["env_studio"]
  },
  "style": ["style_formal", "style_chic", "style_minimalist", "style_glam", "style_edgy"]
}
```

---

### **`backgrounds.json`**
| Field | Type | Required | Tags Used |
|------|------|---------|----------|
| `value` | string | Yes | — |
| `tags.temperature` | array | Yes | `temp_*` |
| `tags.environment` | array | Yes | `env_*` |
| `style` | array | Yes | `style_*` |

**Example**:
```json
{
  "value": "blurred urban background",
  "tags": {
    "temperature": ["temp_hot", "temp_neutral"],
    "environment": ["env_urban", "env_outdoor"]
  },
  "style": ["style_street", "style_casual", "style_chic", "style_edgy", "style_glam"]
}
```

---

### **`lightings.json`**
| Field | Type | Required | Tags Used |
|------|------|---------|----------|
| `value` | string | Yes | — |
| `tags.environment` | array | Yes | `env_*` |
| `tags.light_temperature` | array | Yes | `light_temp_*` |
| `style` | array | Yes | `style_*` |

**Example**:
```json
{
  "value": "soft light",
  "tags": {
    "environment": ["env_indoor", "env_outdoor", "env_natural"],
    "light_temperature": ["light_temp_neutral", "light_temp_warm"]
  },
  "style": [
    "style_casual", "style_formal", "style_soft", "style_sporty",
    "style_chic", "style_vintage", "style_minimalist", "style_street",
    "style_boho", "style_edgy", "style_academic", "style_preppy",
    "style_athleisure", "style_glam"
  ]
}
```

---

## 3. **How to Add a New Style Element**

### **Step-by-Step Template**

```json
{
  "value": "Your descriptive text here",
  "tags": {
    "category1": ["tag_a", "tag_b"],
    "category2": ["tag_x"]
  },
  "style": ["style_x", "style_y"]
}
```

### **Rules**
1. **`value`**: Clear, natural language. Use `{outfit_color}` in outfits.
2. **`tags`**: Must match **exact tag names** from [Style tags](#1-style-tags-overview).
3. **`style`**: Must be valid `style_*` tags.
4. **Arrays**: Use multiple tags when applicable (e.g., multiple environments).
5. **Save & Restart**: Changes take effect after restarting `app.bat`.

---

## 4. **Style Compatibility Engine**  
*How Coherent Prompts Are Generated Automatically*

The **Style Compatibility Engine** is the intelligent core of the image generation system. It **automatically creates visually consistent donor images** by combining physical traits (from `donor_info.csv`) with stylistic options (from `styles_data/`) using a **tag-based filtering pipeline**.

No manual prompt engineering. No random mismatches.  
Every element — outfit, lighting, pose, background — is **selected in sequence**, each one **filtered by the tags of the previous**.

---

### **How It Works: Step-by-Step**

The process begins with two inputs:
1. **Physical traits** of the donor (hair type, hair length, skin tone, etc.)
2. **Available style options** (merged from all JSON files in `styles_data/`)

Then, the engine follows a **strict, logical order** to build the final composition:

---

#### **Step 1: Choose the Scene Anchor**

- **For Full-Body**: Start with a **Location**  
  → Randomly select one from `locations.json`
- **For Portrait**: Start with a **Background**  
  → Randomly select one from `backgrounds.json`

> This becomes the **foundation**. Everything else must be compatible with its `temperature` and `environment` tags.

---

#### **Step 2: Select a Compatible Outfit**

The engine **filters** all outfits (`outfits_fullbody.json` or `outfits_portrait.json`) using:
- `temperature` tags from the location/background
- `environment` tags from the location/background

**Only outfits that match both** are allowed.

**If none match** → Picks a **random fallback**.

---

#### **Step 3: Build Core Style Elements (`_compose_base`)**

Now, using the **selected outfit**, the engine chooses:

| Element | Filtered By | Source |
|--------|-------------|--------|
| **Outfit Color** | Outfit’s `color_clarity`, `color_saturation`, `color_hue`, `color_family` | `outfit_colors.json` |
| **Makeup** | Outfit’s `makeup_intensity` | `makeups.json` |
| **Hairstyle** | **Model’s** `hair_type` + `hair_length` | `hairstyles.json` |
| **Lighting** | Scene’s `environment` | `lightings.json` |
| **Expression** | Style | `expressions.json` |

> **Key**: Hairstyle **respects the models’s real hair** 
---

#### **Step 4: Select a Compatible Pose (Full-Body Only)**

The **expression** is used to filter poses:
- Expression has `emotion` tags (e.g., `emotion_confident`)
- Only poses with **matching `emotion` tags** are allowed

**If none match** → fallback to random pose.

---

**All elements are modular, extensible, and fully documented.**  
Use this guide to understand, modify, or expand the visual language of your donor image generator.

> **Pro Tip**: Use online JSON validators when editing. Invalid syntax will break loading.