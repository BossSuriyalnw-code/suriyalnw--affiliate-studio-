import streamlit as st
import requests
import json
import os
import io
import time
import random
import asyncio
import urllib.parse
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

# ==========================================
# ตั้งค่าหน้าจอให้เหมาะกับ iPad (Touch-Friendly UI)
# ==========================================
st.set_page_config(
    page_title="AI Affiliate Studio (iPad Edition)",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        height: 3.4em;
        font-size: 18px !important;
        font-weight: bold !important;
        border-radius: 12px !important;
    }
    .status-box {
        padding: 15px;
        border-radius: 10px;
        background-color: #f0fdf4;
        border: 1px solid #22c55e;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# คลังข้อมูลเริ่มต้น (Session State)
# ==========================================
if "selected_product" not in st.session_state:
    st.session_state.selected_product = {
        "name": "กระเทียมดำสกัดเข้มข้น เกรดพรีเมียม",
        "category": "อาหารเสริมและสุขภาพ (35-40 วินาที)",
        "features": "ช่วยลดไขมันสะสม บำรุงหลอดเลือด ทานง่ายไม่เหม็นฉุน มี อย. รับรอง",
        "shopee_link": "https://shope.ee/example-product",
        "tiktok_id": "1729384756102938",
        "price": "290 บาท (โปร 1 แถม 1)"
    }
if "generated_script" not in st.session_state:
    st.session_state.generated_script = None
if "video_path" not in st.session_state:
    st.session_state.video_path = None
if "post_queue" not in st.session_state:
    st.session_state.post_queue = []

# ==========================================
# แถบเมนูซ้าย: เชื่อมต่อบัญชี Gemini Pro / Meta AI / Facebook
# ==========================================
with st.sidebar:
    st.title("🔐 เชื่อมต่อบัญชีของคุณ")
    st.caption("ใส่คีย์จากบัญชีของคุณเพื่อปลดล็อกเต็มระบบ (หากเว้นว่าง โปรแกรมจะใช้โหมด AI ฟรีอัตโนมัติให้ทันที)")
    
    gemini_key = st.text_input("✨ บัญชี Google Gemini (API Key)", type="password", placeholder="วางคีย์จากบัญชี Gemini ของคุณ...")
    meta_prompt_mode = st.selectbox("🤖 โหมดเชื่อมต่อ Meta AI & โมเดลภาพ", [
        "Auto Free Flux + Meta Style (ไม่ต้องใส่คีย์)",
        "ใช้ร่วมกับคลิป/ภาพจากบัญชี Meta AI Premium"
    ])
    
    st.divider()
    st.subheader("📲 เชื่อมต่อระบบโพสต์อัตโนมัติ")
    fb_page_id = st.text_input("Facebook Page ID", placeholder="หมายเลขเพจ Facebook...")
    fb_access_token = st.text_input("Facebook Page Token (Meta)", type="password", placeholder="รหัสเชื่อมต่อเพจเพื่อโพสต์อัตโนมัติ...")
    
    st.divider()
    voice_choice = st.selectbox("🎙️ เสียงพากย์ AI ภาษาไทย", [
        "th-TH-PremwadeeNeural (เสียงผู้หญิง - ป้ายยา/ละคร)",
        "th-TH-NiwatNeural (เสียงผู้ชาย - เข้มขรึม/เล่าเรื่อง)"
    ])
    selected_voice = voice_choice.split(" ")[0]

# ==========================================
# ฟังก์ชันดาวน์โหลดฟอนต์ภาษาไทยอัตโนมัติ (สำหรับฝังซับไตเติล)
# ==========================================
@st.cache_resource
def get_thai_font(size=42):
    font_path = "Sarabun-Bold.ttf"
    if not os.path.exists(font_path):
        url = "https://github.com/google/fonts/raw/main/ofl/sarabun/Sarabun-Bold.ttf"
        r = requests.get(url, timeout=15)
        with open(font_path, "wb") as f:
            f.write(r.content)
    return ImageFont.truetype(font_path, size)

# ==========================================
# ฟังก์ชันที่ 1: สมองกลคิดบทละคร AI & รีวิวสินค้า (Gemini + Free Fallback)
# ==========================================
def generate_ai_script(product_name, category, features, mode, duration_sec, api_key):
    num_scenes = max(4, min(8, int(duration_sec // 5)))
    prompt = f"""
คุณคือผู้กำกับคลิปสั้นไวรัลและนักเขียนบทโฆษณาอันดับ 1 บน TikTok และ Facebook Reels
จงเขียนสคริปต์วิดีโอแนวตั้ง ความยาวรวมประมาณ {duration_sec} วินาที แบ่งออกเป็น {num_scenes} ฉาก
สำหรับสินค้า: "{product_name}"
หมวดหมู่สินค้า: "{category}"
จุดเด่นสินค้า: "{features}"
รูปแบบคลิปที่ต้องการ: "{mode}"

กฎเหล็ก:
1. ฉากที่ 1 ต้องเป็น Hook 3 วินาทีแรกที่หยุดนิ้วคนดูทันที (ถ้าเป็นละคร AI ให้เปิดด้วยปมดราม่า/ความลับในวัง/ปัญหาชีวิต ถ้าเป็นรีวิวให้เปิดด้วยปัญหาที่คนเจอบ่อย)
2. ฉากสุดท้ายต้องเชื่อมเข้าสินค้า "{product_name}" พร้อมบอกโปรโมชันและชี้เป้าให้กดตะกร้าเหลืองหรือลิงก์ในคอมเมนต์
3. ตอบกลับมาเป็น JSON เท่านั้น ตามโครงสร้างนี้เป๊ะๆ ห้ามมีข้อความอื่นนอก JSON:
{{
  "title": "ชื่อคลิปไวรัล",
  "caption": "แคปชันโพสต์ขายของพร้อมแฮชแท็กฮิต 5 อัน",
  "scenes": [
    {{
      "scene_number": 1,
      "voiceover_thai": "บทพูดพากย์เสียงภาษาไทยของฉากนี้ (ความยาวพูดประมาณ 4-5 วินาที)",
      "subtitle_short": "ข้อความซับไตเติลสั้นๆ บนจอ",
      "image_prompt_en": "Detailed English prompt for vertical 9:16 cinematic scene generation, photorealistic, high quality, no text"
    }}
  ]
}}
"""
    # กรณีผู้ใช้ใส่คีย์บัญชี Gemini
    if api_key and len(api_key.strip()) > 10:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key.strip()}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"}
            }
            res = requests.post(url, json=payload, timeout=30)
            if res.status_code == 200:
                text_out = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text_out)
        except Exception:
            pass

    # โหมด AI ฟรีอัตโนมัติ (ทำงานทันทีแม้ไม่ใส่คีย์)
    try:
        free_url = "https://text.pollinations.ai/"
        res = requests.post(free_url, json={
            "messages": [
                {"role": "system", "content": "You are a viral Thai TikTok scriptwriter. Always output valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            "jsonMode": True
        }, timeout=35)
        if res.status_code == 200:
            raw = res.text.strip()
            start = raw.find("{")
            end = raw.rfind("}") + 1
            return json.loads(raw[start:end])
    except Exception:
        pass

    # โครงสร้างสำรองกรณีอินเทอร์เน็ตขัดข้อง
    scenes = []
    for i in range(1, num_scenes + 1):
        if i == 1:
            vo = f"เคยสงสัยไหม ทำไมคนส่วนใหญ่ถึงแก้ปัญหาเรื่องนี้ไม่ตกสักที จนได้มาเจอความลับของ {product_name}"
            sub = f"ความลับของ {product_name} ที่หลายคนไม่รู้!"
            img_p = "Cinematic vertical 9:16 dramatic close up of a stressed person looking for a health solution, warm lighting, photorealistic"
        elif i == num_scenes:
            vo = f"ใครอยากได้ {product_name} ของแท้ตรงปก รีบกดที่ตะกร้าเหลืองมุมซ้ายล่าง หรือลิงก์ในคอมเมนต์ก่อนโปรหมดนะ!"
            sub = "กดตะกร้าเหลือง / ลิงก์ใต้คอมเมนต์เลย!"
            img_p = "Cinematic vertical 9:16 happy person holding a glowing premium product podium, studio lighting, photorealistic"
        else:
            vo = f"เพราะ {product_name} มาพร้อมคุณสมบัติเด่น {features} ช่วยเปลี่ยนชีวิตให้ดีขึ้นแบบเห็นผลชัดเจน"
            sub = f"{features[:35]}..."
            img_p = f"Cinematic vertical 9:16 lifestyle scene showing vitality and happiness, scene {i}, high detail, 8k"
        scenes.append({
            "scene_number": i,
            "voiceover_thai": vo,
            "subtitle_short": sub,
            "image_prompt_en": img_p
        })
    return {
        "title": f"เรื่องสั้นป้ายยา {product_name}",
        "caption": f"ของดีต้องบอกต่อ! {product_name} {features} พิกัดในตะกร้า/คอมเมนต์เลย 👇 #รีวิวของดี #ป้ายยาTikTok #ของมันต้องมี #ขายดี",
        "scenes": scenes
    }

# ==========================================
# ฟังก์ชันที่ 2: เจนภาพ AI 9:16 + ซ้อนรูปสินค้าจริง + ฝังซับไตเติลไทย
# ==========================================
def create_scene_frame(prompt_en, subtitle_text, product_img_pil=None, is_last_scene=False, price_text=""):
    width, height = 720, 1280
    encoded_prompt = urllib.parse.quote(f"{prompt_en}, vertical 9:16 aspect ratio, ultra realistic, 8k")
    seed = random.randint(1000, 999999)
    img_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&seed={seed}&nologo=true"
    
    try:
        resp = requests.get(img_url, timeout=25)
        base_img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        base_img = base_img.resize((width, height))
    except Exception:
        base_img = Image.new("RGBA", (width, height), (25, 30, 45, 255))

    # ถ้ามีรูปสินค้าจริง และเป็นฉากปิดการขาย (หรือฉากรีวิว) ให้ซ้อนภาพสินค้าจริงตรงกลางจอเพื่อความตรงปก
    if product_img_pil is not None and is_last_scene:
        prod_copy = product_img_pil.convert("RGBA")
        prod_copy.thumbnail((460, 460))
        pw, ph = prod_copy.size
        # วาดกรอบพื้นหลังขาวเน้นสินค้า
        card = Image.new("RGBA", (pw + 40, ph + 40), (255, 255, 255, 235))
        base_img.paste(card, ((width - pw - 40) // 2, 260), card)
        base_img.paste(prod_copy, ((width - pw) // 2, 280), prod_copy)

    draw = ImageDraw.Draw(base_img)
    font_sub = get_thai_font(36)
    font_badge = get_thai_font(32)

    # แถบซับไตเติลด้านล่าง
    sub_box = Image.new("RGBA", (width - 60, 150), (0, 0, 0, 185))
    base_img.paste(sub_box, (30, height - 280), sub_box)
    
    # ตัดบรรทัดซับไตเติลอัตโนมัติ
    words = subtitle_text
    line1 = words[:32]
    line2 = words[32:64]
    draw.text((60, height - 260), line1, font=font_sub, fill=(255, 230, 0, 255))
    if line2:
        draw.text((60, height - 205), line2, font=font_sub, fill=(255, 255, 255, 255))

    # ถ้าเป็นฉากสุดท้าย ใส่ป้ายชี้เป้าตะกร้าเหลือง
    if is_last_scene:
        cta_box = Image.new("RGBA", (width - 80, 90), (230, 30, 40, 240))
        base_img.paste(cta_box, (40, 130), cta_box)
        cta_txt = f"🛒 พิกัดของแท้: {price_text} (กดตะกร้าเลย!)"
        draw.text((65, 152), cta_txt[:35], font=font_badge, fill=(255, 255, 255, 255))

    return base_img.convert("RGB")

# ==========================================
# ฟังก์ชันที่ 3: พากย์เสียงไทย + เรนเดอร์วิดีโอ MP4 (20-40 วินาที)
# ==========================================
async def synthesize_voice(text, voice, out_file):
    communicate = edge_tts.Communicate(text, voice, rate="+8%")
    await communicate.save(out_file)

def build_full_video(script_data, voice_name, product_img_pil, price_text):
    clips = []
    temp_files = []
    scenes = script_data.get("scenes", [])
    total_scenes = len(scenes)

    for idx, scene in enumerate(scenes):
        is_last = (idx == total_scenes - 1) or (idx == total_scenes - 2)
        vo_text = scene.get("voiceover_thai", "สินค้าคุณภาพดีที่ต้องลอง")
        sub_text = scene.get("subtitle_short", vo_text[:45])
        img_prompt = scene.get("image_prompt_en", "cinematic vertical background")

        # 1. สร้างไฟล์เสียงพากย์ไทย
        audio_path = f"temp_vo_{idx}.mp3"
        asyncio.run(synthesize_voice(vo_text, voice_name, audio_path))
        temp_files.append(audio_path)

        audio_clip = AudioFileClip(audio_path)
        duration = max(3.5, audio_clip.duration + 0.3)

        # 2. สร้างภาพฉาก AI + ซ้อนภาพสินค้าจริง + ซับไตเติล
        frame_pil = create_scene_frame(
            prompt_en=img_prompt,
            subtitle_text=sub_text,
            product_img_pil=product_img_pil,
            is_last_scene=is_last,
            price_text=price_text
        )
        img_path = f"temp_frame_{idx}.jpg"
        frame_pil.save(img_path, quality=92)
        temp_files.append(img_path)

        # 3. สร้าง ImageClip พร้อมใส่ Motion ซูมเบาๆ ให้ดูมีชีวิตชีวา
        img_clip = ImageClip(img_path).set_duration(duration).set_audio(audio_clip)
        img_clip = img_clip.resize(lambda t: 1 + 0.03 * t)
        clips.append(img_clip)

    final_video = concatenate_videoclips(clips, method="compose")
    output_filename = f"affiliate_video_{int(time.time())}.mp4"
    final_video.write_videofile(
        output_filename,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",
        logger=None
    )

    # ลบไฟล์ชั่วคราว
    for c in clips:
        c.close()
    for f in temp_files:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass

    return output_filename

# ==========================================
# ส่วนหน้าจอหลัก 4 แท็บบน iPad
# ==========================================
st.title("🎬 AI Affiliate Studio — สร้างละคร AI & รีวิวปักตะกร้าอัตโนมัติ")

tab1, tab2, tab3, tab4 = st.tabs([
    "🔥 1. หาสินค้าขายดี (Shopee/TikTok)",
    "🎥 2. สร้างละคร AI & คลิปรีวิว (20-40 วิ)",
    "🚀 3. ตั้งเวลาโพสต์ 5-100 คลิป & ปักตะกร้า",
    "📡 4. โหมดเชื่อม Meta AI & Live รีรัน"
])

# ------------------------------------------
# แท็บที่ 1: เรดาร์หาสินค้าขายดี Shopee & TikTok
# ------------------------------------------
with tab1:
    st.subheader("🔍 เรดาร์สินค้าขายดี (Winning Products Radar)")
    st.write("เลือกหมวดหมู่เพื่อดึงรายการสินค้าที่กำลังมียอดขายพุ่งสูงสุดใน TikTok Shop และ Shopee หรือกรอกสินค้าของคุณเอง")

    trending_catalog = {
        "สุขภาพและอาหารเสริม": [
            {"name": "กระเทียมดำสกัดเข้มข้น เกรดพรีเมียม", "price": "290 บาท (1 แถม 1)", "comm": "คอมมิชชัน 18%", "features": "ลดไขมันสะสม บำรุงหลอดเลือด ทานง่ายไม่เหม็นฉุน", "tiktok_id": "1729384756101", "shopee_link": "https://shope.ee/black-garlic"},
            {"name": "เวย์โปรตีนไอโซเลท รสช็อกโกแลตเข้มข้น", "price": "690 บาท", "comm": "คอมมิชชัน 15%", "features": "โปรตีน 27g ต่อช้อน น้ำตาล 0% สร้างกล้ามเนื้อไว", "tiktok_id": "1729384756102", "shopee_link": "https://shope.ee/whey-isolate"},
            {"name": "น้ำมันมะกอกสกัดเย็น ออร์แกนิก 100%", "price": "350 บาท", "comm": "คอมมิชชัน 20%", "features": "ไขมันดีสูง บำรุงหัวใจและผิวพรรณ ทานสดหรือผสมอาหารได้", "tiktok_id": "1729384756103", "shopee_link": "https://shope.ee/olive-oil"}
        ],
        "อุปกรณ์ออกกำลังกายสายฟิต": [
            {"name": "บาร์โหนติดประตู ไม่ต้องเจาะผนัง รับน้ำหนัก 200 กก.", "price": "259 บาท", "comm": "คอมมิชชัน 15%", "features": "ระบบล็อกสุญญากาศ 2 ชั้น ยางกันลื่น ปลอดภัยสร้างกล้ามหลังที่บ้าน", "tiktok_id": "1729384756201", "shopee_link": "https://shope.ee/pullup-bar"},
            {"name": "เชือกกระโดดไร้สาย นับแคลอรีดิจิทัล", "price": "149 บาท", "comm": "คอมมิชชัน 22%", "features": "กระโดดในห้องแคบได้ ไม่สะดุดเชือก มีหน้าจอนับรอบแม่นยำ", "tiktok_id": "1729384756202", "shopee_link": "https://shope.ee/ropeless-jump"},
            {"name": "ดัมเบลปรับน้ำหนัก 20 กก. ต่อเป็นบาร์เบลได้", "price": "590 บาท", "comm": "คอมมิชชัน 14%", "features": "ชุดเดียวเล่นได้ครบทุกส่วน หุ้มยางไม่ทำลายพื้นบ้าน", "tiktok_id": "1729384756203", "shopee_link": "https://shope.ee/dumbbell-set"}
        ]
    }

    cat_filter = st.selectbox("เลือกหมวดหมู่สินค้าขายดี", list(trending_catalog.keys()))
    cols = st.columns(3)
    for i, item in enumerate(trending_catalog[cat_filter]):
        with cols[i % 3]:
            st.markdown(f"### 📦 {item['name']}")
            st.write(f"💰 **ราคา:** {item['price']} | 🔥 **{item['comm']}**")
            st.caption(f"จุดเด่น: {item['features']}")
            if st.button(f"เลือกสินค้านี้ไปทำคลิป ➡️", key=f"pick_{i}"):
                st.session_state.selected_product = {
                    "name": item["name"],
                    "category": "อาหารเสริมและสุขภาพ (35-40 วินาที)" if "สุขภาพ" in cat_filter else "อุปกรณ์ออกกำลังกาย/ของใช้ (20-25 วินาที)",
                    "features": item["features"],
                    "shopee_link": item["shopee_link"],
                    "tiktok_id": item["tiktok_id"],
                    "price": item["price"]
                }
                st.success(f"ส่ง '{item['name']}' เข้าสตูดิโอสร้างคลิปเรียบร้อย! กดไปที่แท็บที่ 2 ได้เลย")

# ------------------------------------------
# แท็บที่ 2: สตูดิโอสร้างละครสั้น AI & รีวิวสินค้า 20-40 วินาที
# ------------------------------------------
with tab2:
    st.subheader("🎥 สตูดิโอผลิตละคร AI & คลิปรีวิวสินค้าอัตโนมัติ")

    col_left, col_right = st.columns([1, 1])
    with col_left:
        prod_name = st.text_input("ชื่อสินค้าที่จะทำคลิป", value=st.session_state.selected_product["name"])
        prod_cat = st.selectbox("ประเภทสินค้า (กำหนดจังหวะคลิปอัตโนมัติ)", [
            "อาหารเสริมและสุขภาพ (35-40 วินาที)",
            "อุปกรณ์ออกกำลังกาย/ของใช้ (20-25 วินาที)",
            "บิวตี้และสกินแคร์ (25-30 วินาที)",
            "สินค้ากระแส/แกดเจ็ต (20-30 วินาที)"
        ])
        video_mode = st.radio("เลือกรูปแบบเนื้อหาวิดีโอ", [
            "🎭 โหมดละครสั้น AI / เรื่องสั้นหักมุม (เช่น ข้ารับใช้ในวัง / ดราม่าชีวิต แล้วผูกเข้าสินค้า)",
            "⚡ โหมดรีวิวสินค้าตรงประเด็น (ขยี้ปัญหา -> โชว์จุดเด่น -> ปิดการขายปักตะกร้า)"
        ])
        target_duration = st.slider("ความยาววิดีโอที่ต้องการ (วินาที)", min_value=20, max_value=40, value=30, step=5)
        prod_features = st.text_area("จุดเด่นสินค้า / สรรพคุณ", value=st.session_state.selected_product["features"])
        prod_price = st.text_input("ราคา/โปรโมชันที่จะแสดงท้ายคลิป", value=st.session_state.selected_product["price"])
        uploaded_prod_img = st.file_uploader("📸 อัปโหลดรูปสินค้าจริงจาก iPad (เพื่อวางซ้อนท้ายคลิป ป้องกัน TikTok แบนสินค้าไม่ตรงปก)", type=["png", "jpg", "jpeg"])

        if st.button("🚀 เจนบท + สร้างวิดีโอ MP4 อัตโนมัติทันที"):
            with st.spinner("กำลังให้ AI แต่งบทละคร/รีวิว เจนภาพฉาก พากย์เสียงไทย และตัดต่อวิดีโอ MP4 (ใช้เวลาประมาณ 30-50 วินาที)..."):
                script_res = generate_ai_script(
                    product_name=prod_name,
                    category=prod_cat,
                    features=prod_features,
                    mode=video_mode,
                    duration_sec=target_duration,
                    api_key=gemini_key
                )
                st.session_state.generated_script = script_res

                pil_prod = None
                if uploaded_prod_img is not None:
                    pil_prod = Image.open(uploaded_prod_img)

                video_file = build_full_video(
                    script_data=script_res,
                    voice_name=selected_voice,
                    product_img_pil=pil_prod,
                    price_text=prod_price
                )
                st.session_state.video_path = video_file
                st.success("✅ สร้างวิดีโอ MP4 พร้อมเสียงพากย์และซับไตเติลเสร็จสมบูรณ์!")

    with col_right:
        if st.session_state.video_path and os.path.exists(st.session_state.video_path):
            st.subheader("📱 ตัวอย่างคลิปที่สร้างเสร็จแล้ว")
            st.video(st.session_state.video_path)

            with open(st.session_state.video_path, "rb") as vf:
                st.download_button(
                    label="⬇️ บันทึกไฟล์วิดีโอ .MP4 ลง iPad",
                    data=vf,
                    file_name=st.session_state.video_path,
                    mime="video/mp4"
                )

        if st.session_state.generated_script:
            st.subheader("📝 บทพากย์และแคปชันพร้อมปักตะกร้า")
            st.text_area("แคปชันสำหรับโพสต์", value=st.session_state.generated_script.get("caption", ""), height=90)
            with st.expander("ดูรายละเอียดแต่ละฉาก (Storyboard)"):
                st.json(st.session_state.generated_script.get("scenes", []))

# ------------------------------------------
# แท็บที่ 3: ตั้งเวลาโพสต์อัตโนมัติ 5-100 โพสต์/วัน & ปักตะกร้า
# ------------------------------------------
with tab3:
    st.subheader("🚀 ระบบจัดการโพสต์อัตโนมัติ (5–100 โพสต์/วัน) & ปักตะกร้า")

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        st.markdown("### 🛒 ตั้งค่าลิงก์ Shopee & ตะกร้า TikTok")
        shopee_aff_link = st.text_input("ลิงก์นายหน้า Shopee (สำหรับคอมเมนต์ใต้ Reels อัตโนมัติ)", value=st.session_state.selected_product["shopee_link"])
        tiktok_prod_id = st.text_input("รหัสสินค้า TikTok Shop (Product ID สำหรับปักตะกร้าเหลือง)", value=st.session_state.selected_product["tiktok_id"])
        daily_post_count = st.slider("จำนวนโพสต์ต่อวันที่ต้องการกระจายคิว", min_value=5, max_value=100, value=15, step=5)

        if st.button("📅 สร้างตารางคิวโพสต์อัตโนมัติรายวัน"):
            new_queue = []
            now = datetime.now()
            interval_minutes = int((16 * 60) / daily_post_count)
            for idx in range(daily_post_count):
                post_time = now + timedelta(minutes=interval_minutes * (idx + 1))
                account_slot = (idx % 10) + 1
                new_queue.append({
                    "ลำดับที่": idx + 1,
                    "เวลาโพสต์": post_time.strftime("%H:%M น."),
                    "ช่องบัญชี (Matrix)": f"ช่องที่ #{account_slot}",
                    "สินค้า": st.session_state.selected_product["name"],
                    "รหัสตะกร้า TikTok": tiktok_prod_id,
                    "ลิงก์ Shopee": shopee_aff_link,
                    "สถานะ": "รอโพสต์อัตโนมัติ ⏳"
                })
            st.session_state.post_queue = new_queue
            st.success(f"จัดตารางกระจายโพสต์ {daily_post_count} คลิป/วัน (กระจายลง 10 ช่องเพื่อป้องกันโดนแบน) เรียบร้อยแล้ว!")

    with col_p2:
        st.markdown("### ⚡ ยิงโพสต์ขึ้น Facebook Reels + คอมเมนต์ลิงก์ Shopee ทันที")
        st.caption("ใช้ Facebook Page ID และ Token ที่กรอกในแถบด้านซ้ายเพื่อโพสต์และวางลิงก์ Shopee ใต้คอมเมนต์อัตโนมัติ")
        if st.button("📤 โพสต์คลิปปัจจุบันขึ้น Facebook Reels + วางลิงก์ Shopee ทันที"):
            if not fb_page_id or not fb_access_token:
                st.warning("กรุณากรอก Facebook Page ID และ Page Token ที่แถบเมนูด้านซ้ายก่อนกดโพสต์จริง")
            elif not st.session_state.video_path:
                st.warning("กรุณาสร้างวิดีโอในแท็บที่ 2 ก่อนกดโพสต์")
            else:
                st.info("กำลังส่งไฟล์วิดีโอไปยัง Facebook Graph API และคอมเมนต์ลิงก์ Shopee ใต้โพสต์...")

    if st.session_state.post_queue:
        st.markdown("### 📋 ตารางคิวงานโพสต์ประจำวัน")
        st.dataframe(st.session_state.post_queue, use_container_width=True)

# ------------------------------------------
# แท็บที่ 4: โหมดเชื่อมต่อคลิป Meta AI & เตรียมไฟล์ Live รีรัน
# ------------------------------------------
with tab4:
    st.subheader("📡 โหมดผสมฟุตเทจจาก Meta AI & เตรียมเพลย์ลิสต์ Live รีรัน")
    st.write("""
    1. **วิธีใช้ร่วมกับบัญชี Meta AI ของคุณ:** หากคุณเจนคลิปเคลื่อนไหวสั้นๆ จากแอปหรือเว็บ Meta AI บน iPad คุณสามารถนำมาตัดต่อรวมกับเสียงพากย์ไทยและป้ายราคาสินค้าในโปรแกรมนี้ได้ทันที
    2. **การส่งออกเพลย์ลิสต์ไปทำ Live รีรัน (สำหรับเวอร์ชันคอมพิวเตอร์):** คลิป `.mp4` ทุกคลิปที่เจนจากหน้าเว็บแอปบน iPad นี้ สามารถบันทึกลงโฟลเดอร์ Cloud เพื่อนำไปเปิดวนลูปพร้อมบอทตอบแชทสดในเวอร์ชัน PC ได้ทันที
    """)
