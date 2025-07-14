# 🤖 Stylus Chatbot API

The **Stylus Chatbot API** allows any project or system to interact with an AI assistant capable of answering questions based on the official documentation of **Stylus**, the WASM smart contract framework for **Arbitrum**.

This API provides a simple HTTP interface to send prompts to a selected open-source language model and receive structured, cleaned responses.

---

## 🌐 Public Endpoint

`POST https://stylus-demo.duckdns.org/api/stylus-chat`

---

## 📥 Request

**Headers**  
`Content-Type: application/json`

**Body (JSON):**

```json
{
  "model": "deepseek-r1:7b",
  "prompt": "How do I deploy a Stylus contract?"
}
```

| Field   | Type   | Required | Description                                           |
|---------|--------|----------|-------------------------------------------------------|
| model   | string | ✅ Yes    | The model to use for inference (see list below)      |
| prompt  | string | ✅ Yes    | The question or instruction sent to the chatbot      |

---

## 📤 Response

```json
{
  "response": "To deploy a Stylus contract, you must first..."
}
```

| Field     | Type   | Description                          |
|-----------|--------|--------------------------------------|
| response  | string | The AI-generated output, cleaned     |

---

## ✅ Supported Models

You can specify any of the following model names in the `model` field:

- `deepseek-r1:7b`
- `deepseek-r1:14b`
- `llama3.1:8b`
- `qwen2.5:32b`

⚠️ Model names must be written exactly as shown. Larger models may have longer response times.

---

## 🧪 Example with `curl`

```bash
curl -X POST https://stylus-demo.duckdns.org/api/stylus-chat \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3.1:8b", "prompt": "How do I deploy a Stylus contract?"}'
```

## 💬 Web Interface

You can also test the AI assistant using a simple graphical interface:

👉 [https://stylus-demo.duckdns.org/assistant](https://stylus-demo.duckdns.org/assistant)

No setup or code required — just open the link and start chatting.


