# Rendu d'un widget HXL dans une conversation Agentforce

Résumé du flux qui permet à l'action `AccountSummaryAction` de rendre son résultat
sous forme de **carte HXL** (nom du compte en gras + séparateur + corps du résumé),
au lieu d'une simple narration texte.

## Illustration

![Rendu du widget HXL dans une conversation Agentforce](images/hxl-agentforce.png)

La carte HXL s'affiche dans le panneau **Architects Employee Agent** (à droite de la
page Data 360) : titre "Alexis Dupont" en gras, séparateur horizontal, puis le corps
du résumé généré par le prompt template.

## Diagramme de séquence

```mermaid
sequenceDiagram
    autonumber
    actor User as Utilisateur
    participant Agent as Employee Agent<br/>(Reasoning Engine)
    participant Action as Agent Action<br/>(AccountSummaryAction)
    participant Apex as Apex @InvocableMethod<br/>summarizeAccounts
    participant Prompt as Prompt Template<br/>Account_Record_Summary_Prompt_Templace
    participant Type as Custom Lightning Type<br/>AccountSummary
    participant Renderer as renderer.json
    participant Widget as uiWidget<br/>@widget/c/accountSummaryWidget

    User->>Agent: Demande un résumé de compte
    Agent->>Action: Invoque l'action (accountId)
    Action->>Apex: summarizeAccounts(requests)
    Apex->>Apex: SELECT Id, Name FROM Account (WITH USER_MODE)
    Apex->>Prompt: generateMessagesForPromptTemplate(accountId)
    Prompt-->>Apex: Texte du résumé (generations[0].text)
    Apex-->>Action: Response.accountSummary : AccountSummary<br/>{ accountName, summary }

    Note over Action,Type: Data Type = @apexClassType/c__AccountSummary<br/>(décrit la FORME de la donnée)

    Action->>Type: Output Rendering = Lightning Type "AccountSummary"<br/>(choisit le RENDU)
    Type->>Renderer: Résout le renderer attaché
    Renderer->>Widget: componentOverrides.$ ->@widget/c/accountSummaryWidget<br/>attrs: accountName, summary
    Widget-->>Agent: Markup UEM (tile/container, tile/text bold, tile/separator)
    Agent-->>User: Carte bordée rendue<br/>(nom en gras + résumé)
```

## Point clé (root cause)

Le rendu ne fonctionnait pas tant que le champ **Output Rendering** de l'agent action
pointait sur le **type Apex brut** `@apexClassType/c__AccountSummary`, qui **n'a aucun
renderer attaché** → le reasoning engine retombait sur la **narration texte** (markdown
`**` littéral, phrases ajoutées type « Let me know… »).

La correction : sélectionner explicitement le **Custom Lightning Type `AccountSummary`**
(le bundle `lightningTypes/AccountSummary/`) dans **Output Rendering**. Ce bundle porte
le `renderer.json` qui redirige vers le widget `@widget/c/accountSummaryWidget`.

| Champ de l'action | Valeur | Rôle |
|---|---|---|
| **Data Type** | `@apexClassType/c__AccountSummary` | Décrit la **forme** de la donnée |
| **Output Rendering** | `AccountSummary` (Lightning Type bundle) | Choisit le **rendu** (porte le renderer) |

> Mnémotechnique : **le Data Type décrit la donnée, l'Output Rendering choisit le rendu.**

## Chaîne d'artefacts

```
AccountSummary.cls (DTO @AuraEnabled: accountName, summary)
        ↓  backing type
@apexClassType/c__AccountSummary
        ↓  lightning:type
lightningTypes/AccountSummary/schema.json  +  renderer.json
        ↓  componentOverrides
@widget/c/accountSummaryWidget
        ↓  attributs mappés
uiWidgets/accountSummaryWidget (schema.json + accountSummaryWidget.json)
```

## Notes

- La décision de rendu vit **côté org** (config de l'agent action), pas dans les
  fichiers locaux du projet — c'est pourquoi republier/réactiver une version ne
  changeait rien tant que l'Output Rendering n'était pas corrigé.
- Le corps `summary` est un blob texte issu du prompt template ; le structurer
  (ex. sous-cartes Sales Orders / Invoices) nécessiterait de renvoyer des données
  structurées (liste d'objets) et d'enrichir le widget en conséquence.
- Surface de rendu : la carte HXL s'affiche dans les surfaces qui supportent le
  rendu des widgets Agentforce.
```
