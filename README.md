config/
    O que o sistema deve fazer.

src/
    Como o sistema faz.

state/
    O que o sistema precisa de lembrar (contém exclusivamente informação que o sistema precisa de recordar entre execuções.)

public/
    O que o sistema publica.


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