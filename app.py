# === FASTAPI Video Processor with Captions, Summary (with Mind Map), and Azure Storage ===

import os
import uuid
import shutil
import subprocess
import json
from datetime import datetime, timedelta
from tempfile import TemporaryDirectory
from typing import List
from pymongo import MongoClient
from azure.storage.blob import BlobServiceClient
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from graphviz import Source
from urllib.parse import quote_plus
import openai
import logging
from fpdf import FPDF
import re
import time
# === CONFIGURATION ===
AZURE_CONN_STR = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_ACCOUNT = "connectlystorage"
AZURE_CONTAINERS = {
    "videos": "videos",
    "transcripts": "transcripts",
    "summary": "summary",
    "images": "summary-image"
}
openai.api_key = os.getenv("OPENAI_API_KEY")

mongo_user = quote_plus("LanTech")
mongo_password = quote_plus("L@nc^ere@0012")
mongo_host = "192.168.48.201"
mongo_port = "27017"
MONGO_URI = f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}/SuperDB?authSource=admin"
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["sample_db"]
collection = db["test"]

# === APP INIT ===
app = FastAPI(title="Video AI Processor")
logger = logging.getLogger("video_processor")
logging.basicConfig(level=logging.INFO)
blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONN_STR)

# === UTILITY FUNCTIONS ===
def upload_to_azure(container: str, file_path: str, blob_name: str):
    blob_client = blob_service_client.get_blob_client(container=container, blob=blob_name)
    with open(file_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)
    return f"https://{AZURE_STORAGE_ACCOUNT}.blob.core.windows.net/{container}/{blob_name}"

def format_srt_time(seconds: float) -> str:
    td = timedelta(seconds=seconds)
    total = int(td.total_seconds())
    millis = int((td.total_seconds() - total) * 1000)
    return f"{str(timedelta(seconds=total)).zfill(8)},{millis:03}"

def create_srt_from_segments(segments: List[dict], output_path: str):
    with open(output_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, start=1):
            start = format_srt_time(seg['start'])
            end = format_srt_time(seg['end'])
            text = seg['text'].strip()
            if text:
                f.write(f"{i}\n{start} --> {end}\n{text}\n\n")

def generate_graph(dot_code: str, output_path: str):
    s = Source(dot_code)
    return s.render(filename=output_path, format="png", cleanup=True)

def save_pdf(content: str, path: str, image_path: str = None):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for line in content.splitlines():
        pdf.multi_cell(0, 10, line)

    if image_path and os.path.exists(image_path):
        pdf.ln(10)
        try:
            pdf.image(image_path, x=None, y=None, w=180)
        except Exception as e:
            print(f"Failed to insert image: {e}")

    pdf.output(path)

def summarize_segment(transcript: str, context: str = ""):
    prompt = f"""
You are a senior documentation and technical writing expert. Your task is to convert the following raw transcript segment into a comprehensive, highly accurate, and formal implementation or study guide based on the subject matter discussed.

The final output must:

- Be structured and formatted according to professional standards for enterprise-level training, onboarding, line pictures, and technical enablement.
- Include step-by-step procedures, clearly numbered and logically ordered.
- Provide real-world tools, technologies, configurations, commands, and screenshots/images (placeholders if needed) relevant to the topic.
- Embed technical examples, use cases, CLI/GUI instructions, and expected outputs or screenshots where applicable.
- Cover common pitfalls, troubleshooting tips, and best practices to ensure full practical understanding.
- Use terminology and instructional depth suitable for readers to gain 100% conceptual and hands-on knowledge of the subject.
- The final document should resemble internal documentation used at organizations like SAP, Oracle, Java, Selenium, AI/ML, Data Science, AWS, Microsoft, or Google — clear, comprehensive, and instructional in tone.

- Additionally, ensure that **for every main topic, you provide 5-10 sentence descriptions** that explain key concepts and their real-world applications. For example, for "Oracle Database" or "Generative AI," give a clear explanation, its use cases, and why it is essential for enterprises. Avoid high-level jargon. Make it practical, applicable, and understandable.

---

OBJECTIVE:

Create a detailed, real-world step-by-step implementation or process guide for [INSERT TOPIC/SUBJECT], designed specifically to support the creation of over 100 technical or comprehension questions. The guide must:

- Reflect real-world tools, technologies, workflows, and industry terminology.
- Break down each phase of the implementation or process logically and sequentially.
- Include practical examples, code snippets (if applicable), key decisions, best practices, and commonly used tools at each step.
- Highlight common challenges or misconceptions, and how they’re addressed in real practice.
- Use terminology and structure that would support SMEs or instructional designers in generating high-quality technical questions based on the guide.
- Avoid abstract or overly generic statements — focus on precision, clarity, and applied knowledge.

---

DOCUMENT FORMAT & STRUCTURE RULES:

1. STRUCTURE
- Use numbered sections and sub-sections (e.g., 1, 1.1, 1.2.1)
- No markdown, emojis, or decorative formatting
- Use plain, formal, enterprise-grade language

2. EACH SECTION MUST INCLUDE:
- A *clear title* and *brief purpose statement*
- *Step-by-step technical or procedural instructions*, including:
    - All relevant tools, platforms, or interfaces used (if any)
    - Any paths, commands, actions, configurations, or API calls involved
    - All required inputs, values, parameters, or dependencies
    - A logical sequence of operations, clearly numbered or separated by actionable steps
    - Tips, warnings, and Important Notes, or expected outcomes where necessary
- **5-10 sentence description** of each main topic, explaining what the concept is, its use cases, and real-world applications. This should be clear and concise for technical audiences to understand why the topic is essential and how it fits into practical workflows.

3. VALIDATION

- Describe how to confirm success (e.g., Expected Outputs, System or Health Checks, Technical and Functional Verifications, Visual Indicators, Fallback/Error Conditions indicators)

4. TROUBLESHOOTING (if applicable)

- Clearly list frequent or known issues that may arise during or after the procedure
- Describe the conditions or misconfigurations that typically lead to each issue
- Provide step-by-step corrective actions or configuration changes needed to resolve each problem
- Mention specific file paths, log viewer tools, console commands, or dashboard areas where errors and diagnostics can be found
- Include example error codes or system messages that help in identifying the issue

5. BEST PRACTICES

- You are a senior technical writer. Based on the following transcript or topic, create a BEST PRACTICES section suitable for formal technical documentation, onboarding materials, or enterprise IT guides.
- Efficiency improvements (e.g., time-saving configurations, automation tips)
- Security or compliance tips (e.g., encryption, IAM roles, audit logging)
- Standard operating procedures (SOPs) used in enterprise environments
- Avoided pitfalls and why they should be avoided
- Format the content using bullet points or short sections for clarity and actionability.
- Avoid vague, obvious, or overly general suggestions — focus on real-world, practical insights derived from field experience or best-in-class implementation norms.

6. CONCLUSION
- Summarize what was implemented or discussed
- Confirm expected outcomes and readiness indicators

---

IMPORTANT:
If the input contains any values such as usernames, IP addresses, server names, passwords, port numbers, or similar technical identifiers — replace their actual content with generic XML-style tags, while preserving the sentence structure and purpose. For example:

- Replace any specific IP address with: <ip>
- Replace any actual password or secret with: <password>
- Replace any actual hostname with: <hostname>
- Replace any actual port number with: <port>
- Replace any username with: <username>
- Replace any email with: <email>

Do NOT alter the sentence structure, meaning, or flow — keep the language intact while swapping the actual values with tags
Do not display or retain real values — just show the placeholder tag. Maintain the original meaning and flow of the instructions.
Format the output as clean, professional documentation, suitable for inclusion in implementation guides, SOPs, or training materials.
Highlight any placeholders in a way that makes it easy for the user to identify where to substitute their own values later.

---

Also:
- Cross-check all tools, commands, file paths, service names, APIs, and utilities with reliable, real-world sources (e.g., official vendor documentation, widely accepted best practices).

 1. If something appears ambiguous, incorrect, or outdated, correct it to its current, supported version.
 2. Use only commands, APIs, or tool names that are verifiably valid and relevant to the topic context.
- Consolidate duplicate or fragmented instructions:
 1. If a step or process is repeated across segments, merge them into a single, complete, and accurate version.
 2. Remove redundancy and preserve the most detailed and correct version of each step.
 3. Do NOT include deprecated or unverifiable content:
 4. Exclude outdated commands, legacy references, or tools no longer maintained.
 5. Replace such content with modern equivalents where available.

- Output the final result as a formal technical guide, with:
  1. Clear section headings
  2. Correct and tested commands/scripts
  3. Accurate tool names and workflows
  4. Logical flow suitable for developers, engineers, or IT teams

---

COMBINED INPUT:
\"\"\"{transcript}\n\n{context}\"\"\"

---

FINAL INSTRUCTION:
Return only the fully formatted implementation or process guide includes below

- A clear, descriptive title
- A concise purpose statement or overview
- Prerequisites and tools required
- Numbered step-by-step instructions with:
   1. Commands, paths, configuration settings, or code blocks (as needed)
   2. GUI or CLI actions explained clearly
   3. Expected inputs, parameters, or options
   4. Confirmation of success (outputs, logs, tests, or validation steps)
   5. Troubleshooting (common issues, causes, and resolutions — if applicable)
   6. Best Practices (efficiency, reliability, security — if applicable)
   7. **Include a mind map diagram in DOT format enclosed in triple backticks at the end**
   8. **Insert chart/diagram placeholders inline to represent where the visual mind map image should appear**

- Replace any real usernames, IP addresses, passwords, ports, or hostnames with <username>, <ip>, <password>, <port>, or <hostname> where needed.
- Eliminate all redundant or outdated, abused content. Only use valid and current tools and commands.

End Document with Standardized "Suggested Next Steps" Note  
*Suggested next steps: No specific next steps mentioned in this segment.*
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",  # Updated to valid model (gpt-4.1-nano is not a known OpenAI model)
            messages=[
                {"role": "system", "content": "You are a technical documentation assistant trained to summarize training meetings."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=3000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[ERROR] Summary generation failed: {e}")
        return "Summary generation failed."
# === MAIN PROCESSING ===
async def process_video(video_path: str, meeting_id: str, user_id: str):
    with TemporaryDirectory() as workdir:
        compressed = os.path.join(workdir, "compressed.mp4")
        audio = os.path.join(workdir, "audio.wav")

        subprocess.run(["ffmpeg", "-y", "-i", video_path, "-c:v", "libx264", "-crf", "35", "-preset", "ultrafast", "-c:a", "aac", "-b:a", "64k", compressed], check=True)
        subprocess.run(["ffmpeg", "-y", "-i", compressed, "-ar", "16000", "-ac", "1", "-vn", audio], check=True)

        with open(audio, "rb") as f:
            transcript_obj = openai.Audio.translate("whisper-1", file=f, response_format="verbose_json")
        transcript_text = "".join([seg["text"] for seg in transcript_obj["segments"]])
        segments = transcript_obj["segments"]

        srt_path = os.path.join(workdir, "captions.srt")
        create_srt_from_segments(segments, srt_path)

        captioned = os.path.join(workdir, "captioned.mp4")
        safe_srt_path = srt_path.replace(os.sep, "/").replace(":", "\\:")
        subtitles_filter = f"subtitles='{safe_srt_path}'"
        subprocess.run(["ffmpeg", "-y", "-i", compressed, "-vf", subtitles_filter, "-c:v", "libx264", "-c:a", "aac", captioned], check=True)

        summary = summarize_segment(transcript_text)

        dot_code = None
        image_path = os.path.join(workdir, "summary_graph.png")
        image_generated = False

        try:
            dot_match = re.search(r"```dot\s*(.*?)```", summary, re.DOTALL)
            if dot_match:
                dot_code = dot_match.group(1).strip()
                summary = re.sub(r"```dot\s*.*?```", "[Mind Map Diagram Below]", summary, flags=re.DOTALL).strip()
        except Exception as e:
            logger.warning(f"DOT extraction failed: {e}")

        if dot_code:
            generate_graph(dot_code, image_path[:-4])
            image_generated = True

        transcript_path = os.path.join(workdir, "transcript.pdf")
        summary_path = os.path.join(workdir, "summary.pdf")
        save_pdf(transcript_text, transcript_path)
        save_pdf(summary, summary_path, image_path)

        video_url = upload_to_azure(AZURE_CONTAINERS["videos"], captioned, f"{meeting_id}_{user_id}_captioned.mp4")
        transcript_url = upload_to_azure(AZURE_CONTAINERS["transcripts"], transcript_path, f"{meeting_id}_{user_id}_transcript.pdf")
        summary_url = upload_to_azure(AZURE_CONTAINERS["summary"], summary_path, f"{meeting_id}_{user_id}_summary.pdf")
        image_url = upload_to_azure(AZURE_CONTAINERS["images"], image_path, f"{meeting_id}_{user_id}_summary_graph.png")

        collection.insert_one({
            "meeting_id": meeting_id,
            "user_id": user_id,
            "video_url": video_url,
            "transcript_url": transcript_url,
            "summary_url": summary_url,
            "image_url": image_url,
            "timestamp": datetime.now()
        })

        return {
            "status": "success",
            "video_url": video_url,
            "transcript_url": transcript_url,
            "summary_url": summary_url,
            "summary_image_url": image_url
        }

# === ROUTES ===
@app.post("/upload/")
async def upload(file: UploadFile = File(...), meeting_id: str = Form(...), user_id: str = Form(...)):
    try:
        existing = collection.find_one({"meeting_id": meeting_id, "user_id": user_id})
        if existing:
            return {
                "status": "already_processed",
                "video_url": existing.get("video_url"),
                "transcript_url": existing.get("transcript_url"),
                "summary_url": existing.get("summary_url"),
                "summary_image_url": existing.get("image_url"),
                "message": "This video has already been processed."
            }

        with TemporaryDirectory() as tmp:
            temp_path = os.path.join(tmp, file.filename)
            with open(temp_path, "wb") as f:
                shutil.copyfileobj(file.file, f)

            result = await process_video(temp_path, meeting_id, user_id)
            return JSONResponse(content=result)

    except Exception as e:
        logger.exception("Upload failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def home():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/health")
def health():
    return {"status": "healthy"}
