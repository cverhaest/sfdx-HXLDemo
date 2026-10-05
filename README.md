# sfdx-HXLDemo — HXL Widget rendering demo

Démonstration du rendu d'un widget **HXL** (Hypertext Lightning) dans deux surfaces :

| Surface | Invocateur | Chemin de rendu |
|---|---|---|
| **Conversation Agentforce** | Employee Agent (Reasoning Engine) | Lightning Type `AccountSummary` → renderer → widget |
| **Agent externe (Claude Desktop)** | Serveur MCP `CVERMCPServer` | Lightning Type `AccountSummaryResult` → renderer → widget |

Dans les deux cas, le résultat final est une **carte bordée** affichant le nom du compte en gras et le résumé généré par IA dans le corps.

---

## Ce que fait le projet

### Fonctionnalité principale

L'action `AccountSummaryAction` génère un résumé en langage naturel d'un compte Salesforce :

1. Reçoit un `accountId` en entrée
2. Interroge le nom du compte (`SELECT Id, Name FROM Account WITH USER_MODE`)
3. Invoque le **Prompt Template** `Account_Record_Summary_Prompt_Templace` via `ConnectApi.EinsteinLLM`
4. Retourne un payload `AccountSummary { accountName, summary }`

Ce payload est rendu sous forme de carte HXL dans la conversation — et non comme narration texte — grâce aux Custom Lightning Types et au widget HXL.

---

## Architecture

### Artefacts clés

```
classes/
  AccountSummary.cls                    DTO Apex (@AuraEnabled : accountName, summary)
  AccountSummaryAction.cls              Action invocable (@InvocableMethod) + outil MCP global

lightningTypes/
  AccountSummary/                       Lightning Type pour le chemin Agentforce natif
    schema.json                           lightning:type = @apexClassType/c__AccountSummary
    renderer.json                         → @widget/c/accountSummaryWidget (attrs directs)

  AccountSummaryResult/                 Lightning Type pour le chemin agent externe (MCP)
    schema.json                           enveloppe top-level { actionName, isSuccess, outputValues }
    renderer.json                         → @widget/c/accountSummaryWidget (via outputValues.accountSummary.*)

  AccountSummaryOutputValues/           Type intermédiaire : forme du champ outputValues
    schema.json                           { accountSummary: @apexClassType/c__AccountSummary }

uiWidgets/
  accountSummaryWidget/
    accountSummaryWidget.json           Markup HXL : tile/container + tile/text (h2 bold) + tile/separator + tile/text (body)
    schema.json                         Déclaration des attributs accountName et summary

mcpServerDefinitions/
  CVERMCPServer.mcpServerDefinition-meta.xml
                                        Serveur MCP custom exposant AccountSummaryAction,
                                        un Flow de classification de sentiments,
                                        et un Prompt Template de documentation.
                                        Lie l'outil AccountSummaryAction à la ressource UI
                                        ui://widget/lightningType/c__AccountSummaryResult
```

### Les deux chemins de rendu

**Chemin Agentforce natif**
- L'action est configurée dans l'agent avec `Output Rendering = AccountSummary` (le Lightning Type bundle)
- Le renderer lit les attributs directement : `{!$attrs.accountName}`, `{!$attrs.summary}`

**Chemin agent externe (Claude Desktop / MCP)**
- L'action est exposée comme outil MCP via `CVERMCPServer`
- Le serveur MCP enveloppe la réponse Apex dans `{ actionName, isSuccess, outputValues: { accountSummary: {...} } }`
- La balise `<uiResource>accountSummary</uiResource>` dans la définition de l'outil + le bloc `<resources>` pointant vers `ui://widget/lightningType/c__AccountSummaryResult` déclenchent le rendu HXL
- Le renderer lit les attributs via le chemin d'enveloppe : `{!$attrs.outputValues.accountSummary.accountName}`

> Documentation détaillée dans [`docs/`](docs/).

---

## Org cible

Définie dans `.env` (voir `.env.example`).

| Variable | Description |
|---|---|
| `SF_ORG_ALIAS` | Username ou alias SF CLI de l'org |
| `SF_INSTANCE_URL` | URL d'instance (`https://<org>.my.salesforce.com`) |

---

## Déploiement

```bash
# Déployer tous les métadonnées sur l'org (remplacer par la valeur de SF_ORG_ALIAS dans .env)
sf project deploy start --target-org <SF_ORG_ALIAS>

# Vérifier le statut
sf project deploy report
```

Après déploiement, activer `CVERMCPServer` dans **Setup → Hosted MCP Servers** si ce n'est pas déjà fait.

---

## Claude Desktop — Configuration initiale

Copier `.env.example` en `.env` à la racine du projet et renseigner les valeurs :

```bash
cp .env.example .env
# éditer .env : SF_CLIENT_ID, SF_INSTANCE_URL
```

| Variable | Description |
|---|---|
| `SF_CLIENT_ID` | Consumer Key de l'External Client App sur l'org |
| `SF_INSTANCE_URL` | URL d'instance de l'org (`https://<org>.my.salesforce.com`) |
| `SF_MCP_SERVER_KEY` | Nom du serveur dans `claude_desktop_config.json` (défaut : `salesforce-hxl-cvermcp`) |

> Le fichier `.env` n'est pas commité (listé dans `.gitignore`).

### External Client App — prérequis OAuth

| Champ | Valeur |
|---|---|
| Callback URL | `http://localhost:8085/callback` |
| Scopes | `mcp_api refresh_token` |
| Méthode | PKCE obligatoire (`code_challenge_method=S256`) |

## Claude Desktop — Rafraîchir le token MCP

Le token Bearer expire après ~12h. Pour le renouveler sans copier-coller manuel :

```bash
python3 scripts/sf-mcp-auth.py
```

Le script :
1. Lit `SF_CLIENT_ID` et `SF_INSTANCE_URL` depuis `.env`
2. Ouvre le navigateur sur le flux OAuth PKCE
3. Attend le callback sur `localhost:8085`
4. Met à jour directement `~/Library/Application Support/Claude/claude_desktop_config.json`
5. Crée un backup `.json.bak` avant toute modification

**Après le script : relancer Claude Desktop** pour que le nouveau token soit pris en compte.

---

## Documentation

| Fichier | Contenu |
|---|---|
| [`docs/HXL-widget-rendering-agentforce-action.md`](docs/HXL-widget-rendering-agentforce-action.md) | Diagramme de séquence — chemin Agentforce natif |
| [`docs/HXL-widget-rendering-external-agent.md`](docs/HXL-widget-rendering-external-agent.md) | Diagramme de séquence — chemin agent externe (Claude Desktop / MCP) |
