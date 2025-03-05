import os
import requests
import json
from datetime import datetime

BRANCH_NAME = os.getenv("BRANCH_NAME")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
WORKFLOW_NAME = os.getenv("WORKFLOW_NAME")
VALID_TEAMS = os.getenv("VALID_TEAMS").split()
REPOSITORY_NAME = os.getenv("GITHUB_REPOSITORY")
SAVE_JSON_TO = os.getenv("SAVE_JSON_TO", "build/teams.json")

HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

def get_last_successful_workflow_run_timestamp():
    """Obtém o timestamp do último workflow bem-sucedido"""

    try:
        url = f"https://api.github.com/repos/{REPOSITORY_NAME}/actions/workflows"

        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            print(f"Erro na API de workflows: {response.status_code} - {response.text}")
            return None

        workflows = response.json().get("workflows", [])
        workflow_id = next((wf["id"] for wf in workflows if wf["name"] == WORKFLOW_NAME), None)

        if not workflow_id:
            print(f"Workflow '{WORKFLOW_NAME}' não encontrado.")
            return None

        url = f"https://api.github.com/repos/{REPOSITORY_NAME}/actions/workflows/{workflow_id}/runs"
        params = {"status": "completed", "conclusion": "success", "per_page": 1}
        response = requests.get(url, headers=HEADERS, params=params)

        if response.status_code != 200:
            print(f"Erro na API de runs do workflow: {response.status_code} - {response.text}")
            return None

        runs = response.json().get("workflow_runs", [])
        for run in runs:
            if run["conclusion"] == "success":
                return run["created_at"]
    except Exception as e:
        print(f"get_last_successful_workflow_run_timestamp {e}")
        return None

    return None

def get_merged_prs_since(timestamp):
    """Busca PRs mergeados desde o último workflow bem-sucedido"""
    try:
        url = f"https://api.github.com/repos/{REPOSITORY_NAME}/pulls"
        params = {"state": "closed", "base": BRANCH_NAME, "per_page": 100}

        response = requests.get(url, headers=HEADERS, params=params)
        if response.status_code != 200:
            print(f"Erro na API de PRs: {response.status_code} - {response.text}")
            return []

        prs = response.json()
        filtered_prs = []
        timestamp_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00")) if timestamp else None

        for pr in prs:
            merged_at = pr.get("merged_at")
            if merged_at:
                merged_at_dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
                if timestamp_dt and merged_at_dt > timestamp_dt:
                    filtered_prs.append({"number": pr["number"], "title": pr["title"]})

        if not filtered_prs:
            print("❌ Nenhum PRs mergeados após o último workflow")
            return []

        print("✅ PRs mergeados após o último workflow:")
        for pr in filtered_prs:
            print(f"🔹 PR #{pr['number']} - {pr['title']}")

        return filtered_prs
    except Exception as e:
        print(f"❌ Erro ao buscar PRS: {e}")

    return []

def get_teams_from_last_successfull_run(prs):
    """Obtem o nome de todos os times que fizeram alteraçoes desde a ultima execução"""
    try:
        recent_teams = []
        for pr in prs:
            parts = pr['title'].split("[")
            if len(parts) > 1:
                team = parts[1].split("]")[0].strip()
                if team.lower() != "devops":
                    recent_teams.append(team)

        return [team for team in VALID_TEAMS if team in recent_teams]
    except Exception as e:
        print(f"❌ Erro ao listar arquivos e criar buildfile: {e}")

    return []

def save_teams_json(teams = []):
    if not teams:
        print(f"❌ Nenhum time valido encontrado, salvando json vazio!")

    with open(SAVE_JSON_TO, 'w') as teamsfile:
        json.dump({"teams": teams}, teamsfile, indent=2)

if __name__ == "__main__":
    if not all([BRANCH_NAME, GITHUB_TOKEN, WORKFLOW_NAME, VALID_TEAMS, REPOSITORY_NAME, SAVE_JSON_TO]):
        raise ValueError("Faltam variáveis de ambiente obrigatórias!")

    print("Iniciando processo de busca de workflows, prs, times...")
    print(f"BRANCH_NAME: {BRANCH_NAME}")
    print(f"VALID_TEAMS: {VALID_TEAMS}")
    print(f"SAVE_JSON_TO: {SAVE_JSON_TO}")
    print(f"WORKFLOW_NAME: {WORKFLOW_NAME}")
    print(f"REPOSITORY_NAME: {REPOSITORY_NAME}")

    last_success_run_timestamp = get_last_successful_workflow_run_timestamp()
    if not last_success_run_timestamp:
        print(f"❌ Nenhum workflow encontrado!")
        save_teams_json()
        exit(0)

    prs = get_merged_prs_since(last_success_run_timestamp)
    if not prs:
        print(f"❌ Nenhum PR encontrado!")
        save_teams_json()
        exit(0)

    teams = get_teams_from_last_successfull_run(prs)
    save_teams_json(teams)