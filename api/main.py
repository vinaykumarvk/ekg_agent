from fastapi import FastAPI, HTTPException
from api.schemas import AskRequest, AskResponse
from api.settings import settings
from agents.ekg_agent import EKGAgent
from openai import OpenAI
import pickle, json

app = FastAPI(title="EKG Agent API")

# Load your graph/by_id/name_index as you do today
G         = None  # e.g., pickle.load(open("data/kg/G.pkl","rb"))
by_id     = {}    # e.g., json.load(open("data/kg/by_id.json"))
name_index= {}    # e.g., json.load(open("data/kg/name_index.json"))

client = OpenAI(api_key=settings.OPENAI_API_KEY)

@app.post("/answer", response_model=AskResponse)
def answer(req: AskRequest):
    try:
        agent = EKGAgent(
            client=client, vs_id=req.vectorstore_id,
            G=G, by_id=by_id, name_index=name_index,
            preset_params=req.params or {}
        )
        res = agent.answer(req.question)
        return AskResponse(markdown=res.get("markdown",""),
                           sources=res.get("curated_chunks") or res.get("sources"),
                           meta={"export_path": res.get("export_path"),
                                 "model": res.get("model_used")})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
