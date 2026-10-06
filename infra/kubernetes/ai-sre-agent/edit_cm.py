import json

with open("s:/Shyam/Grill/Working on/projects/Devops-Project/Devops-Project-Worked-By-Me/django-notes-app/infra/kubernetes/ai-sre-agent/cm.json", "r") as f:
    data = json.load(f)

data["data"]["__init__.py"] = "from .ai_sre_agent import *"

# Remove fields we don't want when applying
for k in ["creationTimestamp", "resourceVersion", "uid"]:
    data["metadata"].pop(k, None)

with open("s:/Shyam/Grill/Working on/projects/Devops-Project/Devops-Project-Worked-By-Me/django-notes-app/infra/kubernetes/ai-sre-agent/cm.json", "w") as f:
    json.dump(data, f, indent=2)
