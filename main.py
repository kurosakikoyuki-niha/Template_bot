import discord
from discord import app_commands
import os
import json
import re
from dotenv import load_dotenv
from typing import Dict

# --- 설정 및 환경 변수 로드 ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
ALLOWED_USERS = [1457950425381736570, 1317810556891304057] # 관리자 ID
RULES_FILE = 'rules.json'

def load_rules() -> Dict[str, str]:
    """외부 JSON 파일에서 규칙 템플릿을 로드합니다."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), RULES_FILE)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception as e:
                print(f"Error loading rules.json: {e}")
                return {}
    return {}

# --- 버튼 및 뷰 클래스 ---
class RuleButton(discord.ui.Button):
    def __init__(self, rule_id: str, label: str, uid: str, img_url: str):
        # 버튼 라벨을 Rule #n 형식으로만 표시
        display_label = f"Rule #{rule_id}" if rule_id.isdigit() else f"Ban - {rule_id}"
        btn_style = discord.ButtonStyle.secondary if rule_id.isdigit() else discord.ButtonStyle.danger
        super().__init__(label=display_label, style=discord.ButtonStyle.secondary)
        self.rule_id = rule_id
        self.reason_text = label
        self.uid = uid
        self.img_url = img_url

    async def callback(self, interaction: discord.Interaction):
        # 최종 명령어 생성
        generated_command = f"/warn user: {self.uid} reason: {self.reason_text} attachment: {self.img_url}" if self.rule_id.isdigit() else f"/ban user: {self.uid} reason: {self.reason_text}"
        
        # 새로운 메시지가 아닌 기존 메시지를 수정하여 결과 출력 (임베드 제거)
        await interaction.response.edit_message(
            content=f"\n```\n{generated_command}\n```",
            view=None  # 명령어가 생성되면 버튼 뷰를 제거
        )

class RulePickerView(discord.ui.View):
    def __init__(self, uid: str, img_url: str, rules: Dict[str, str]):
        super().__init__(timeout=180) # 3분 후 버튼 비활성화
        # 로드된 규칙들을 바탕으로 버튼 동적 생성
        for rule_id, reason in rules.items():
            self.add_item(RuleButton(rule_id, reason, uid, img_url))

# --- 봇 클라이언트 클래스 ---
class TemplateBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        # 메시지 내용을 읽어 UID를 추출해야 하므로 message_content 필요
        intents.message_content = True 
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f'Template Bot Online: {self.user}')

bot = TemplateBot()

@bot.tree.context_menu(name="Get Warn Command")
async def generate_template(interaction: discord.Interaction, message: discord.Message):
    """로그 메시지에서 UID와 이미지를 추출하여 규칙 선택 버튼을 띄웁니다."""
    
    if interaction.user.id not in ALLOWED_USERS:
        return await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)

    # 1. 메시지 본문에서 UID 추출 (17~20자리 숫자 패턴)
    uid_match = re.search(r'\d{17,20}', message.content)
    # 만약 임베드 안에 UID가 있다면 임베드 내용도 검색
    if not uid_match and message.embeds:
        for embed in message.embeds:
            content = f"{embed.title} {embed.description} " + " ".join([f"{f.name} {f.value}" for f in embed.fields])
            uid_match = re.search(r'\d{17,20}', content)
            if uid_match: break

    uid = uid_match.group(0) if uid_match else "Unknown_UID"

    # 2. 이미지 URL 추출 (첨부파일 또는 임베드 이미지)
    img_url = "No_Image_URL"
    if message.attachments:
        img_url = message.attachments[0].url
    elif message.embeds:
        for embed in message.embeds:
            if embed.image:
                img_url = embed.image.url
                break
            if embed.thumbnail:
                img_url = embed.thumbnail.url
                break

    # 3. 규칙 파일 로드 및 버튼 뷰 전송
    rules = load_rules()
    if not rules:
        return await interaction.response.send_message("'rules.json' has not found or empty.", ephemeral=True)

    view = RulePickerView(uid, img_url, rules)
    await interaction.response.send_message(
        content=f"Target User UID: `{uid}`\nSelect Rule to Apply:", 
        view=view, 
        ephemeral=True
    )

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("에러: .env 파일에 DISCORD_TOKEN이 설정되지 않았습니다.")
