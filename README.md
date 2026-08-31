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

Fetcher
    → dados normalizados

Cleaner
    → Article[]

Deduplicator
    → Article[] sem duplicados

PublishedState
    → filtra artigos já publicados

FeedGenerator
    → RSS XML em memória

Source
  ↓
Fetcher
  ↓
raw dict[]
  ↓
Cleaner
  ↓
Article[]
  ↓
Deduplicator
  ↓
PublishedState.unpublished()
  ↓
Article[] novos
  ↓
FeedGenerator.generate()
  ↓
RSS XML
  ↓
FileOutput.write()
  ↓
PublishedState.mark_published()

A ordem dos feeds na configuração define a prioridade quando um mesmo artigo pertence a vários feeds.