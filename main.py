from typing import Union
from fastapi import FastAPI
import json
import re
from openai import OpenAI
from dotenv import load_dotenv
import os


app = FastAPI()

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)


def split_text_into_sentences(text: str) -> dict:
    if not text or not text.strip():
        return {
            "sentences": []
        }

    try:
        prompt = f"""
กรุณาแบ่งข้อความต่อไปนี้เป็นประโยคที่สมบูรณ์ โดยคำนึงถึงบริบทและความหมาย:

\"{text}\"

กฎการแบ่ง:
1. แบ่งตามเครื่องหมายวรรคตอน (. ! ? ฯลฯ)
2. แบ่งตามความหมายที่สมบูรณ์
3. รักษาบริบทของประโยคให้ครบถ้วน
4. ไม่แบ่งชื่อเฉพาะ วันที่ ตัวเลข ที่เป็นหน่วยเดียวกัน
5. รักษาการขึ้นบรรทัดใหม่ที่สำคัญ

แสดงผลเป็น JSON array ของ string โดยไม่ต้องอธิบายเพิ่มเติม:
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "คุณเป็นผู้เชี่ยวชาญในการแบ่งประโยคภาษาไทยและภาษาอังกฤษ ให้ผลลัพธ์เป็น JSON array เท่านั้น"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=2000
        )

        content = response.choices[0].message.content
        # print(f'Content: {content}')
        try:
            sentences = json.loads(content)
            if isinstance(sentences, list):
                sentences = [s.strip() for s in sentences if s.strip()]
                return {
                    "sentences": sentences
                }
        except json.JSONDecodeError:
            # print("⚠️ ไม่สามารถแปลง JSON ได้ ตกกลับไปใช้ fallback")
            pass

        fallback = fallback_sentence_split(text)
        return {
            "sentences": fallback
        }

    except Exception as e:
        # print("❌ เกิดข้อผิดพลาด:", e)
        return {
            "sentences": fallback_sentence_split(text)
        }

def fallback_sentence_split(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    sentences = re.split(r'(?<=[.!?ฯ])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) == 1:
        return [line.strip() for line in text.splitlines() if line.strip()]
    return sentences

def apply_corrections(original_text, corrections):
    """
    Apply corrections to the original text using AI

    Args:
        original_text (str): Original text that needs correction
        corrections (str): Correction suggestions in format: wrong_word,correct1|correct2|correct3

    Returns:
        str: Corrected text
    """

    # If no corrections needed, return original text
    if not corrections or corrections.strip() == "":
        return original_text

    # Create prompt for correction
    prompt = f"""
ข้อความต้นฉบับ: {original_text}

คำแนะนำการแก้ไข: {corrections}

กรุณาแก้ไขข้อความต้นฉบับตามคำแนะนำที่ให้มา โดย:
1. เลือกคำที่เหมาะสมที่สุดจากตัวเลือกที่แนะนำ
2. แก้ไขเฉพาะคำที่ระบุในคำแนะนำเท่านั้น
3. คงรูปแบบและโครงสร้างประโยคเดิมไว้
4. ไม่เพิ่มหรือลดคำใดๆ นอกเหนือจากการแก้ไข
5. ตอบเฉพาะข้อความที่แก้ไขแล้วเท่านั้น ไม่ต้องอธิบาย

ข้อความที่แก้ไขแล้ว:"""

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "คุณคือผู้ช่วยแก้ไขข้อความภาษาไทย ทำหน้าที่แก้ไขข้อความตามคำแนะนำที่ได้รับ โดยเลือกคำที่เหมาะสมที่สุดและคงรูปแบบเดิมไว้"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0,
            seed=123
        )

        corrected_text = completion.choices[0].message.content or original_text
        return corrected_text.strip()

    except Exception as error:
        # print(f'OpenAI API Error: {error}')
        return original_text

def correct_full_text(sentences, proofs):
    """
    Correct full text by applying corrections to each sentence

    Args:
        sentences (list): List of original sentences
        proofs (list): List of correction suggestions for each sentence

    Returns:
        str: Full corrected text
    """
    corrected_sentences = []

    for i, (sentence, proof) in enumerate(zip(sentences, proofs)):
        corrected_sentence = apply_corrections(sentence, proof)
        corrected_sentences.append(corrected_sentence)
        # print(f"แก้ไขประโยคที่ {i+1}: {corrected_sentence}")

    # Join sentences back together
    full_corrected_text = " ".join(corrected_sentences)
    return full_corrected_text

def get_consistent_response(text, proper_names):
    """
    Get consistent spell checking response for Thai text

    Args:
        text (str): Thai text to check
        proper_names (list): List of proper names that should not be corrected

    Returns:
        str: Correction suggestions in format: wrong_word,correct1|correct2|correct3
    """

    # Prepare proper names string
    proper_names_str = ', '.join(proper_names)

    # Create prompt
    prompt = f"""
ประโยค: {text}
ตรวจหาคำผิดทั้งหมดในประโยคข้างต้นตามลำดับดังนี้
1. พิจารณาทีละคำอย่างละเอียด
2. ตรวจสอบบริบทภาพรวม
3. แสดงผลในรูปแบบ: คำผิด,คำถูก1|คำถูก2|คำถูก3 (สามารถเสนอได้สูงสุด 3 คำเท่านั้น) (ขึ้นบรรทัดใหม่เมื่อมีคำผิดหลายคำ)
กรุณาตรวจสอบทุกคำอย่างละเอียด โดยเฉพาะ:
1. คำที่สะกดผิด (พยัญชนะ / ตัวสะกด / วรรณยุกต์ผิด)
2. คำที่เขียนติดกันแต่ควรแยก
3. คำที่เขียนแยกแต่ควรติดกัน
4. คำที่ไม่เหมาะสมกับบริบท
5. คำที่คาดว่าจะพิมพ์ผิด
6. เครื่องหมาย / ให้แทนที่ด้วยคำว่า "หรือ"
ข้อสำคัญ:
- พิจารณาบริบทของประโยคก่อนแนะนำการแก้ไข
- ถ้าคำนั้นถูกต้องตามบริบทแล้ว ไม่ต้องแนะนำการแก้ไข
- ถ้ามีหลายคำที่ถูกต้องและเหมาะสมกับบริบท ให้เลือกเฉพาะ 3 คำที่ดีที่สุดเท่านั้น
- ห้ามอธิบายหรือใส่คำอื่นเพิ่มเติม
- ห้ามละเว้นคำผิดที่พบ
- 🔥 ห้ามแก้ไขชื่อเฉพาะต่อไปนี้โดยเด็ดขาด: {proper_names_str}
- 🔥 ถ้าพบคำใดคำหนึ่งในรายการชื่อเฉพาะ ให้ข้ามไปเลยไม่ต้องแนะนำการแก้ไข"""

    try:
        # Call OpenAI API
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "คุณคือนักพิสูจน์อักษรภาษาไทยที่เชี่ยวชาญ มีหน้าที่ตรวจสอบการสะกดคำและความเหมาะสมตามบริบทให้ถูกต้องตามหลักภาษาไทย สำหรับแต่ละคำผิดให้เสนอคำแนะนำไม่เกิน 3 ตัวเลือกเท่านั้น และห้ามแก้ไขชื่อเฉพาะที่ผู้ใช้กำหนดไว้โดยเด็ดขาด"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0,
            seed=422
        )

        content = completion.choices[0].message.content or ''

        return content

    except Exception as error:
        print(f'OpenAI API Error: {error}')
        return ''

@app.get("/")
def read_root():
    return {"Hello": "Proof Reading User! :)"}


@app.get("/proof/{text}")
def proof(text):
    result = split_text_into_sentences(text)
    proper_names = ["แพทองธาร"]
    sentences = result["sentences"]
    proof = []
    # # ตรวจสอบแต่ละประโยค
    for i, sentence in enumerate(sentences, 1):
        result_proof = get_consistent_response(sentence, proper_names)
        proof.append(result_proof)

        
    corrected_text = correct_full_text(sentences, proof)
    return {"before":text,
            "after":corrected_text}
    # print(f"{i}. {sentence}")
    # print(f'Proof: {result_proof}')
# def read_item(item_id: int, q: Union[str, None] = None):
#     return {"item_id": item_id, "q": q}