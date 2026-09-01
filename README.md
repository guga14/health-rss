- Fluxo mínimo:

                 FONTES
        ┌──────────┼──────────┐
        ↓          ↓          ↓
      RSS        HTML        API
        │          │          │
        └──────────┼──────────┘
                   ↓
              FETCH / READ
                   ↓
             NORMALIZAÇÃO
                   ↓
              ARTIGOS[]
                   ↓
           GERAR RSS / XML
                   ↓
          ┌─────────────────┐
          │  feed-saude.xml │
          │  feed-farmacia.xml
          │  feed-investigacao.xml
          │       ...       │
          └─────────────────┘
                   ↓
             GIT COMMIT
                   ↓
             GITHUB REPO
                   ↓
            GITHUB PAGES
                   ↓
              URLs RSS
                   ↓
                 RSS APP

  