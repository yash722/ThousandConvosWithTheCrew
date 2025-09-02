# 🏴‍☠️ Straw Hat Crew Agent Simulation  

This project simulates conversations between the **Straw Hat Pirates** (One Piece characters) using **Microsoft AutoGen**, **OpenAI GPT models**, and a custom **Group Chat Manager**.  
You can roleplay with the crew aboard the *Thousand Sunny* and have them respond in-character, remembering past messages in the session.  

---

## 🚀 Features
- ✅ Multi-agent conversation: each Straw Hat acts as an autonomous agent.  
- ✅ Personality-driven responses: loaded from `strawhat_personalities.json`.  
- ✅ Group Chat Manager orchestrates the flow of dialogue.  
- ✅ User can join the crew as a participant ("User Agent").  
- ✅ Supports continuous chat loops (or one-off prompts).  
- ✅ Extendable to Discord for roleplay in a channel.  

---

## 📦 Requirements
- Python **3.10+**
- Install dependencies:
  ```bash
  pip install -r requirements.txt

- requirements
    - autogen-core
    - autogen-ext
    - openai
    - rich
    - pydantic
    - python-dotenv

## Setup
- Clone this repo
    ```
    git clone https://github.com/yash722/ThousandConvosWithTheCrew.git
    cd ThousandConvosWithTheCrew
    ```
- Create a virtual environment with the requirements
- Get your environment variables
    - OPENAI_API_KEY=your_openai_api_key_here
- Prepare Straw Hat personalities JSON (Given here but you can use the script to generate real time personas)
- Start the crew chat
    ```
    python thousand_sunny.py
    ```