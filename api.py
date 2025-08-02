import json
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Configurações
BOT_TOKEN = "8191885274:AAGA5_UwWzkFFzvloC_O3i8JVCziQS4gkXE"
ADMIN_IDS = [8183673253]
VIP_USERS = [8183673253]
ALLOWED_GROUPS = [-4781844651]
DEFAULT_DAILY_LIMIT = 30
API_URL_TEMPLATE = "https://likes.ffgarena.cloud/api/v2/likes?uid={uid}&amount_of_likes=100&auth=vortex"

# Estado simples em memória (perdido a cada execução no Vercel)
allowed_groups = set(ALLOWED_GROUPS)
group_usage = {}
user_data = {}
promotion_message = ""
command_enabled = True

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_today():
    from datetime import date
    return date.today().strftime("%Y-%m-%d")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Bot rodando via webhook! Use /like <uid> para enviar likes.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📘 HELP MENU

Comandos:
/like <uid> - Enviar likes
/check - Seu uso hoje
/groupstatus - Status do grupo
/remain - Quantidade de usuários hoje
"""
    await update.message.reply_text(help_text)

async def like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.message.chat.type
    if chat_type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Comando só funciona em grupos.")
        return

    group_id = update.effective_chat.id
    if group_id not in allowed_groups:
        await update.message.reply_text("❌ Grupo não autorizado.")
        return

    # Reset diário simplificado
    today = get_today()
    usage = group_usage.get(group_id, {"count":0, "date": None})
    if usage["date"] != today:
        usage = {"count": 0, "date": today}
    if usage["count"] >= DEFAULT_DAILY_LIMIT:
        await update.message.reply_text("❌ Limite diário de likes do grupo atingido!")
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text("⚠️ Uso correto: /like <uid>")
        return

    uid = args[0]
    user_id = update.effective_user.id
    is_vip = user_id in VIP_USERS

    if not is_vip:
        user_info = user_data.get(user_id, {"date": None, "count": 0})
        if user_info["date"] == today and user_info["count"] >= 1:
            await update.message.reply_text("⛔ Você já usou seu like gratuito hoje.")
            return
        user_data[user_id] = {"date": today, "count": user_info["count"]}

    # Chamada API externa
    try:
        response = requests.get(API_URL_TEMPLATE.format(uid=uid))
        data = response.json()
        logger.info(f"API response: {data}")
    except Exception as e:
        logger.error(f"Erro na API: {e}")
        await update.message.reply_text("🚨 Erro na API! Tente novamente mais tarde.")
        return

    required_keys = ["nickname", "region", "level", "likes_antes", "likes_depois", "sent"]
    if not all(k in data for k in required_keys):
        await update.message.reply_text("⚠️ UID inválido ou erro ao obter detalhes.")
        logger.warning(f"Resposta incompleta da API: {data}")
        return

    if data.get("sent") == "0 likes":
        await update.message.reply_text("⚠️ UID já atingiu o máximo de likes hoje.")
        return

    if not is_vip:
        user_data[user_id]["count"] += 1
    usage["count"] += 1
    group_usage[group_id] = usage

    text = (
        f"✅ Likes enviados com sucesso!\n\n"
        f"👤 Nome: {data['nickname']}\n"
        f"🆔 UID: {uid}\n"
        f"🌍 Região: {data['region']}\n"
        f"🎮 Nível: {data['level']}\n"
        f"🤡 Antes: {data['likes_antes']}\n"
        f"🗿 Depois: {data['likes_depois']}\n"
        f"🎉 Enviados: {data['sent']}"
    )
    if promotion_message:
        text += f"\n\n📢 {promotion_message}"

    await update.message.reply_text(text)

# Setup da aplicação e handlers
application = ApplicationBuilder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("like", like))

# Função handler para o Vercel (endpoint serverless)
async def handler(request):
    if request.method != "POST":
        return {
            "statusCode": 405,
            "body": "Method Not Allowed"
        }

    body = await request.json()
    update = Update.de_json(body, application.bot)
    await application.update_queue.put(update)
    return {
        "statusCode": 200,
        "body": "OK"
  }
