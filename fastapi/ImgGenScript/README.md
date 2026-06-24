# Image Generator - Script

## Step-by-Step Installation

### Step 1: Clone the Repository
Navigate to your desired directory and press `Win` + `X`, then select `Terminal` to open `Windows PowerShell`.

![Open Windows PowerShell](resources/cmd_01.png)

![Windows PowerShell](resources/cmd_02.png)

Clone the project repository:

```bash
git clone https://github.com/BabynovaIA/ImgGenScript.git
cd ImgGenScript
```
![Copy Repository](resources/cmd_03.png)

This will create a folder called `ImgGenScript` where all the program files are located.

---
### Step 2: Copy the images

Navigate to the root directory of your project. Inside, you'll find a folder named `files`. Within `files`, there's another folder called `images`.

This is where you should copy the folders containing the model reference images. **These folders must follow the naming pattern `OVOD#####` (e.g., `OVOD00001`, `OVOD00042`).** Any folders that do not match this pattern will be ignored by the script.

---
### Step 3: Configure model Information

In the project's root directory, navigate to the `files` folder, then enter the `csv` folder. Here, you'll find a file named `model_info.csv`. This file stores crucial information about the models used for image generation.

The `model_info.csv` file must contain the following columns:

* **`vreproID`**: The VRepro ID of the model, following the pattern `OVOD#####` (e.g., `OVOD00001`, `OVOD00042`).
* **`age`**: The model's age.
* **`skinTone`**: The model's skin tone (e.g., "White," "Brunette," "Black"). The model consistently favors lighter skin tones. For models with darker skin tones, it's advisable to use modifiers to ensure accurate representation. **The default value is "White."**
* **`eyeColor`**: The model's eye color. For models with light-colored eyes, it's recommended to avoid using only "Blue," "Green," or "Amber," as these can result in overly vibrant and unrealistic eye colors. Consider using modifiers like "Dull", "Dull greenish gray" or "Dull bluish gray" to soften the color. **The default value is "Brown."**
* **`hairColor`**: The model's hair color. **The default value is "Dark brown."**
* **`hairType`**: The model's hair type (e.g., "Straight", "Wavy", "Curly", "Coily").
* **`hairLength`**: The model's hair length (e.g., "Short", "Shoulder length", "Long"). **The default value is "Long."**
* **`hairstyleType`**: The model's hairstyle (e.g., "Loose", "Ponytail", "Braid", "Bun"). This field is optional and can be left blank. If a value is provided, all images will have the same hairstyle. If left empty, each image will have a different hairstyle.
* **`clothingStyle1`**:  
  **Primary aesthetic style** for the model's wardrobe. Must match one of the valid `style_*` tags defined in the system [Avaliables Styles](#available-styles).  
  - The system **filters outfits, makeup, poses, and lighting** compatible with this style.  
  - If **not provided or invalid**: Defaults to `style_casual`.  

* **`clothingStyle2`**:  
  **Secondary aesthetic style** (optional). Allows for **hybrid or layered styling** (e.g., `style_casual` + `style_street`).  
  - If provided: The system **expands the pool** of compatible traits by including elements from both styles.  
  - If **not provided or invalid**: **Ignored** — only `clothingStyle1` is used.  

* **`bodyType`**: The model's body type (e.g., "Straight", "Equal shoulders and hips with a defined waist", "Wider hips than shoulders", "Wider shoulders than hips", "Wider middle section"). 
* **`bodyComplexion`**: The model's general body complexion (e.g., "Slim," "Thick", "Curvy", "Voluptuous"). This term refers to the overall structure of the body beyond just the `bodyType`. It's important to note that the model tends to favor slender bodies, and its perception of body size is often leaner than expected.
* **`bustType`**: The model's bust size. The model generally favors stylized bodies with smaller breasts. The use of modifiers (e.g., "small," "medium," "large," or descriptive terms like "petite," "ample") is highly recommended to accurately represent the desired bust type. **The default value is "Proportional."**
* **`thighType`**: The model's thigh size (e.g., "Slender", "Curvy", "Thick"). **The default value is "Proportional."**
* **`expression`**: The model's facial expression (e.g., "happy", "dreamy", "neutral"). This field is optional and can be left blank. If a value is provided, all images will have the same expression. If left empty, each image will have a different expression.
* **`specialCharacteristics`**: Special characteristics of the model (e.g., "freckles", "moles", "scars"). This field is optional and can be left blank. If a value is provided, it will be included in the positive prompt.

---
### Step 4: Run the Application

In the root directory of the project, you will find an executable batch file named `app.bat`. This script automates the setup and execution of the application.

When you run `app.bat`, it performs the following actions:

1.  **Virtual Environment Setup**: It checks for an existing Python virtual environment (`.venv`). If one is not found, it automatically creates it.
2.  **Activate Virtual Environment**: It activates the created (or existing) virtual environment.
3.  **Install Dependencies**: It looks for a `requirements.txt` file in the root directory. If found, it installs all necessary Python dependencies listed in that file.
4.  **Execute Main Script**: Finally, it runs the main application script, `main.py`, starting the project.

To start the application, simply double-click `app.bat` or run it from your command line:

```bash
app.bat
```
---
## How to Use the Application Interface

The application features a straightforward graphical user interface (GUI) designed for ease of use in managing image generation tasks.

**Interface Overview:**

![Application Interface](resources/App.png)

### Core Functionality

* **Generation Type Selection (`Fullbody` and `Portrait` buttons):**
    * You must select at least one of these buttons to specify the type of images you wish to generate.
    * Both "Fullbody" and "Portrait" can be selected simultaneously to generate both types of images for the specified models.

* **Fullbody Options:**
    * **Text Box:** Enter the number of generation cycles you want to perform for each selected model for full-body images.
        * Entering `-1` will initiate an indefinite generation process for full-body images.
    * **`Use Pose` Button:** When activated, this button adds an extra generation step. It first **generates an image to serve as a reference pose**, which the application then uses to copy the pose for the final generated full-body image.
    * **`Hands Refiner` Button:** Activating this adds an extra step to the generation process, specifically focused on improving the appearance and realism of the hands in the final image.

    * **`Amateur Effect` Button:** Activates a post-processing stage that applies an effect to the images to give them a more "amateur" or less professional appearance, adjusting colors and adding other effects.

* **Portrait Options:**
    * **Text Box:** Similar to the Fullbody Options, this box allows you to specify the number of generation cycles for portrait images for each selected model.
        * Entering `-1` will initiate an indefinite generation process for portrait images.

* **Model List:**
    * **Text Box:** This box allows you to specify the model IDs for which you want to generate images.
    * Enter model IDs as comma-separated numbers (e.g., `609, 1673, 100`).
    * **Important**: Omit the `OVOD` prefix; only the five-digit number is required.
    * If this box is left empty, the application will perform generation for *all* model folders found in the `files/images` directory.

### Control Buttons & Hotkeys

* **`Start Execution` Button:** Click this button to begin the image generation process based on your selected options.
* **`Stop Execution` Button:** Click this button to safely stop the ongoing generation process. This action will also close the program.

* **Keyboard Hotkeys:**
    * **`a`**: Pressing 'a' will export all images that have been marked with "OK" (by adding "OK" to their filename during a review process) within their respective model folders in `files/images`. These approved images will be moved to the `approved` folder in the project's root directory, maintaining their original folder structure.
    * **`d`**: Toggles between the normal (light) and dark mode themes for the application interface.
    * **`q`**: Safely exits the application. It is highly recommended to use this hotkey for exiting rather than forcefully closing the window (e.g., with Alt+F4 or by clicking the 'X' button), to ensure all processes are terminated correctly.

### Program Logs

* The large black area on the right-hand side of the interface will display real-time logs and output messages from the program, providing feedback on the generation progress and any encountered issues.
---

## How to Generate a Batch of Images

### Step 0: Input Data Preparation
Before starting the generation process, it's essential to ensure the correct arrangement of model data. model information (age, eye color, hair color, hair type...) must reside in the `model_info.csv` file, located in the `files/csv/` directory. Additionally, model reference images must be organized in an individualized folder for each model, following the naming convention `OVOD#####` (where `#####` corresponds to the `VRepro` code), within the `files/images` directory.

The system supports a maximum of six (6) reference images per model. If a folder contains more than six images, only the first six in alphabetical order will be processed; the rest will be ignored.

---

### Step 1: Select the Image Type to Generate

Image generation requires explicit selection of the desired output type: **`Fullbody`** or **`Portrait`**. Omitting this selection will result in a Warning and the interruption of the generation process.

![Application Interface - Type Checkbox](resources/step_01_01.png)

#### **No Type Selected**

If no image type has been selected, any attempt to start the generation will trigger a warning, and the process will not execute.

![Type Checkbox - None Selected](resources/step_01_02.png)

#### **"Fullbody" Selected**

By selecting this option, the system will exclusively generate full-body images.

![Type Checkbox - Fullbody Selected](resources/step_01_03.png)

#### **"Portrait" Selected**

This option enables the exclusive generation of portrait images.

![Type Checkbox - Portrait Selected](resources/step_01_04.png)

#### **Both Types Selected**

When both options are selected, the generation will proceed alternately, producing batches of full-body and portrait images consecutively.

![Type Checkbox - Both Selected](resources/step_01_05.png)

### Step 2: Configure Generation Options

To execute the generation, it's crucial to define key parameters, especially the number of image batches to generate for each selected type. By default, this parameter is set to 1, producing a single batch of images. This value can be any positive integer or -1 to enable unlimited generation.

![Application Interface - Generation Options](resources/step_02_01.png)

It's critical to note that if an image type was not selected in Step 1, its associated generation options will be ignored during the process.

#### Fullbody Options
Full-body images have a default batch count of 1. Additionally, there's a 

- **`Use Pose`** checkbox. When this option is enabled, images will be generated randomly using a reference pose from images stored in the `files/reference/fullbody` folder or a new reference image will be generated on runtime. By default, this option is disabled, and the pose reference is derived from the textual descriptions specified in the `poses.json` located in the `backend/cfg/styles_data/` folder. This means each generated image will select a random pose.

- **`Hands Refiner`** checkbox. When this option is enabled, a section is added to the workflow to improve the generation of hands in the images.

- **`Amateur Effect`** checkbox. When this option is enabled, a post-processor is applied so that the images have a more amateur aesthetic.

![Generation Options - Fullbody Options](resources/step_02_02.png)

#### Portrait Options
Portrait images have a default batch count of 1. For this image type, the reference pose is always randomly selected from images located in the `files/reference/portrait` folder. In other words, each generated portrait image will use a random pose obtained from an existing image.

![Generation Options - Portrait Options](resources/step_02_03.png)

### Step 3: Model Selection (Optional)

Optionally, you can specify which models to generate images for. This is done by entering the model's identification number (omitting the `OVOD` prefix) and separating different identifications with commas (`,`). By default, this field is empty, meaning the system will generate images for all models with an `OVOD#####` folder in the `files/images` directory.

![Generation Options - model Selection](resources/step_03_01.png)

For example, entering "609, 4200, 100" will cause the system to look for folders `OVOD00609`, `OVOD04200`, and `OVOD00100` within `files/images`. It's imperative that the actual model photographs reside in folders with the complete `VRepro` nomenclature. The absence of these folders will result in an error.

![model Selection](resources/step_03_02.png)

### Step 4: Start Generation

To initiate the generation process, simply click the **`Start Execution`** button.

![Generation Options - Start](resources/step_04_01.png)

During execution, this button will be disabled. Generated images will be saved in subfolders named `fullbody` or `portrait`, as appropriate, within the respective model's `OVOD#####` folder in the `files/images` directory.

### Step 5: Stop Generation

To stop the ongoing generation, click the **`Stop Execution`** button.

![Generation Options - Stop](resources/step_05_01.png)

This action will safely halt the image generation process and close the application.

---
## Configuration

This section explains how to configure the image generation system. All settings are centralized in **`config.yaml`** and **`backend/cfg/styles_data/`**, allowing full control over workflows, models, and visual styles **without modifying code**.

---

### 1. `config.yaml` – Core Settings & Workflow Control
The main configuration file is located at:

```
backend/cfg/config.yaml
```
This file controls **server addresses, model parameters, sampling settings, and generation pipelines**.

#### Key Sections:

| Section | Purpose |
|-------|--------|
| **`comfyui_server_address` / `fastapi_server_address`** | Network addresses for ComfyUI and FastAPI. Change if running in Docker, remote server, or non-default ports. |
| **`img_max_dimension`** | Max resolution (default: `1024`). All input/reference images are resized to this. |
| **`max_retries` / `retries_delay_seconds`** | Retry logic for failed generations. |
| **`interrupt_after_seconds`** | Auto-interrupt long-running jobs to prevent hangs. |
| **Prompt template files** | Paths to `.txt` prompt templates (positive/negative/detailer/hands). |
| **`portrait:` / `fullbody:`** | **Per-generation-type settings**: workflow JSON, checkpoint model, ControlNet, IP-Adapter, FaceID, detailer, etc. |

> **Tip**: You only need to edit `config.yaml` if:
> - You're changing **models** (checkpoint, ControlNet, CLIP Vision, etc.)
> - You're adjusting **sampling steps, CFG, denoise**
> - You're tweaking **FaceID/IP-Adapter weights**

---

### 2. `styles_data/` – Tag-Based Style System

The image generation system utilizes a **tag-driven style architecture** to automatically create coherent, context-aware prompts. All visual style options are defined in the backend/cfg/styles_data/ directory using **JSON files** and a **semantic tag system**.

#### Structure and Definition
All style elements are defined in JSON files located within `backend/cfg/styles_data/`:

```
backend/cfg/styles_data/
├── outfits_portrait.json
├── outfits_fullbody.json
├── outfit_colors.json
├── hairstyles.json
├── makeups.json
├── expressions.json
├── poses.json
├── locations.json
├── backgrounds.json
└── lightings.json
```

> **Key Benefit**: Add new styles, colors, or locations by editing the JSON files in `styles_data/`. Restart `app.bat` to apply changes.

#### Automatic Prompt Generation

This system **eliminates the need for manual prompt engineering** through two automatic steps:

1.  **Automatic Combination:** Style profiles are **automatically combined** to form initial prompt components.
2.  **Contextual Filtering:** The resulting combinations are then filtered using **contextual compatibility rules** (temperature, environment, hue, saturation, emotion, etc.). This process generates **coherent, context-aware prompts**.


#### Available Styles

| Style | Description | Typical Use Case | Compatible With |
|-------|-------------|------------------|-----------------|
| **`style_casual`** | Relaxed, everyday wear with comfort in mind. Simple, functional, and approachable. | Daily life, urban walks, casual meetups | Jeans, t-shirts, sneakers, natural lighting, urban/natural backgrounds |
| **`style_formal`** | Structured, polished, and professional. Tailored fits, clean lines, elegant fabrics. | Business, events, portraits | Blazers, dress shirts, heels, studio/minimalist backgrounds, neutral tones |
| **`style_soft`** | Gentle, romantic, flowy, and feminine. Light fabrics, pastel tones, delicate details. | Dreamy portraits, outdoor settings | Flowy dresses, loose blouses, soft lighting, natural/scenic backgrounds |
| **`style_sporty`** | Athletic, dynamic, performance-oriented. Breathable fabrics, bold logos, functionality. | Fitness, outdoor activity | Activewear, sneakers, bright/neon colors, natural light, parks/gyms |
| **`style_chic`** | Modern, refined, effortlessly stylish. High attention to detail and silhouette. | Fashion editorials, urban sophistication | Tailored tops, minimalist jewelry, studio or textured walls |
| **`style_vintage`** | Retro-inspired, nostalgic, warm tones. Textures, patterns, and classic cuts. | Artistic portraits, storytelling | Earth tones, linen, wood interiors, golden hour light |
| **`style_minimalist`** | Clean, uncluttered, monochrome or neutral. Focus on form and negative space. | Studio shots, product-like clarity | White/gray/black, solid backgrounds, soft studio light |
| **`style_street`** | Urban, bold, youth-driven. Layering, graphics, attitude. | City life, social media | Denim, sneakers, graffiti walls, overcast/fluorescent light |
| **`style_boho`** | Free-spirited, earthy, layered. Natural fabrics, patterns, accessories. | Festivals, travel, nature | Maxi skirts, crochet, terracotta, plants, warm light |
| **`style_edgy`** | Provocative, sharp, dramatic. Leather, asymmetry, intense contrasts. | Nightlife, editorial | Black, deep reds, smokey makeup, neon/urban night settings |
| **`style_academic`** | Intellectual, preppy, timeless. Cardigans, pleated skirts, classic accessories. | Campus, libraries, professional creative | Navy, maroon, sage, wood-paneled rooms, soft natural light |
| **`style_preppy`** | Polished casual with heritage influence. Clean lines, collared shirts, loafers. | Ivy league, upscale casual | Pastels, navy, blazers, manicured lawns, campus settings |
| **`style_athleisure`** | Comfortable performance wear styled for daily life. Sleek, modern, functional. | Gym-to-street, wellness culture | Leggings, hoodies, sneakers, yoga studios, parks |
| **`style_glam`** | High-impact, luxurious, red-carpet ready. Shine, bold makeup, dramatic poses. | Events, nightlife, editorial | Deep colors, sequins, heels, studio with dramatic lighting |
| **`style_playful`** | Fun, youthful, expressive. Bright colors, dynamic poses, lighthearted mood. | Social content, youth branding | Neon, graphic tees, playful expressions, urban pop settings |

---

### 3. `prompts/` - Prompt Templates

Located in the `backend/cfg/prompts/` directory, these `.txt` files contain the base prompts used for image generation.

* **`fullbody_positive_prompt.txt`**: This file contains the positive prompt template used for generating full-body images.
* **`portrait_positive_prompt.txt`**: This file holds the positive prompt template specifically for generating portrait images.
* **`negative_prompt.txt`**: This is the universal negative prompt applied during image generation to guide the AI away from undesired elements.
* **`detailer_positive_prompt.txt`**: Contains the positive prompt for the face detailer, enhancing facial features.
* **`detailer_negative_prompt.txt`**: Contains the negative prompt for the face detailer, used to refine facial details by excluding unwanted artifacts.
* **`detailer_wildcard_prompt.txt`**: This file holds wildcard prompts specifically for the face detailer, allowing for more dynamic and varied facial expressions or features.

> **Note**: Use placeholders like `{fullbody_outfit}`, `{lighting}`, `{expression}` — the system replaces them with tag-generated text.

---

### 4. `reference/` Reference Images
The `files/reference/` directory, located in the project's root, stores images used as pose references during image generation. This directory contains two subfolders:

- `fullbody/`: Images in this folder are used as pose references for full-body (legacy) image generation when the "Use Pose" option is activated.
- `portrait/`: Images in this folder are always used as a pose reference for portrait image generation.

**Important considerations for reference images**:

- All reference images must be **1024x1024 pixels**.
- Each reference image must contain **only one person**.
- Failure to provide reference images in these folders will result in an error during generation when they are required.

---

## Directory Structure
```
.
├── app.bat
├── approved.bat
├── approved.py
├── main.py 
├── README.md 
├── requirements.txt
├── backend/
│   ├── app/
│   ├── cfg/
│   │   ├── post_processor/
│   │   │   ├── blocks.json
│   │   │   └── styles.json
│   │   ├── prompts/
│   │   │   ├── detailer_negative_prompt.txt
│   │   │   ├── detailer_positive_prompt.txt
│   │   │   ├── detailer_wildcard_prompt.txt
│   │   │   ├── fullbody_positive_prompt.txt
│   │   │   ├── portrait_positive_prompt.txt 
│   │   │   ├── negative_prompt.txt
│   │   │   ├── hands_positive_prompt.txt
│   │   │   └── hands_negative_prompt.txt
│   │   ├── styles_data/
│   │   │   ├── backgrounds.json
│   │   │   ├── expressions.json
│   │   │   ├── hairstyles.json
│   │   │   ├── lightings.json
│   │   │   ├── locations.json
│   │   │   ├── makeups.json
│   │   │   ├── outfit_colors.json
│   │   │   ├── outfits_portrait.json
│   │   │   └── poses.json
│   │   ├── workflow/
│   │   │   ├── fullbody.json
│   │   │   └── portrait.json
│   │   └── cfg.json
│   ├── logs/
│   └── src/
│       ├── batch/
│       │   ├── orchestrator.py
│       │   ├── processors/
│       │   │   └── processor.py
│       │   ├── services/
│       │   │   ├── comfyui_restarter.py
│       │   │   ├── composition_builder.py
│       │   │   ├── data_loader.py
│       │   │   ├── post_processor_service.py
│       │   │   ├── state_manager.py
│       │   │   └── workflow_builder.py
│       │   └── utils/
│       │       └── hair_classifier.py
│       ├── clients/
│       │   ├── base_client.py
│       │   ├── comfyui_client.py
│       │   ├── fastapi_client.py
│       │   └── utils/
│       │       ├── comfyui_web_socket.py
│       │       └── http.py
│       ├── composition/
│       │   ├── composition.py
│       │   ├── physical_traits.py
│       │   ├── style_definition.py
│       │   ├── style_traits.py
│       │   ├── trait_data_loader.py
│       │   └── trait.py
│       ├── config/
│       │   ├── fullbody_settings.py
│       │   ├── portrait_settings.py
│       │   └── settings.py
│       ├── generator/
│       │   ├── image_generator.py
│       │   └── components/
│       │       ├── builders/
│       │       │   └── prompt_builder.py
│       │       ├── handlers/
│       │       │   ├── image_handler.py
│       │       │   └── memory_manager.py
│       │       └── workflow/
│       │           ├── comfyui_workflow.py
│       │           └── workflow_manager.py
│       ├── logger/
│       │   └── logger.py
│       ├── post_processor/
│       │   └── post_processor.py
│       ├── request/
│       │   ├── base_request.py
│       │   ├── fullbody_request.py
│       │   ├── portrait_request.py
│       │   ├── request_factory.py
│       │   ├── data/
│       │   │   ├── appearance_data.py
│       │   │   └── model_data.py
│       │   ├── scene/
│       │   │   ├── fullbody_scene_data.py
│       │   │   ├── portrait_scene_data.py
│       │   │   └── scene_data.py
│       │   └── workflow/
│       │       ├── fullbody_workflow_data.py
│       │       ├── portrait_workflow_data.py
│       │       └── workflow_data.py
│       └── utils/
│           ├── collection.py
│           ├── file.py
│           ├── image.py
│           ├── io.py
│           ├── others.py
│           └── random.py
└── files/
  ├── approved/
  ├── csv/
  │   └── model_info.csv
  ├── images/
  └── reference/
      ├── fullbody
      └── portrait
```
---
## FAQ & Troubleshooting

### How do I add new reference poses?

To add new reference poses for image generation, simply copy your new reference images into the appropriate subfolder within the `files/reference/` directory:

* For **full-body pose references**, place your images in `files/reference/fullbody/`.
* For **portrait pose references**, place your images in `files/reference/portrait/`.

Remember, all reference images must be **1024x1024 pixels** and contain **only one person** to ensure proper functionality and avoid errors during generation.