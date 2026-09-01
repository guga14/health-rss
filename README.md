- Fluxo:

                 FETCH
                   ↓
             raw articles
                   ↓
                CLEAN
                   ↓
                Article
                   ↓
             DEDUPLICATE
                   ↓
              unique Article
                   ↓
          ┌─────────────────┐
          │ Published State │
          └────────┬────────┘
                   ↓
             artigos novos
                   ↓
             FeedGenerator
                   ↓
                RSS XML
                   ↓
             Output/Publish
                   ↓
              sucesso?
              /       \
            não       sim
             ↓         ↓
         não altera   mark
          state     published

A ordem dos feeds na configuração define a prioridade quando um mesmo artigo pertence a vários feeds.