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

sources
   ↓
articles novos
   ↓
deduplicate
   ↓
PublishedState
   ↓
new_articles
   ↓
ler RSS existente
   ↓
existing + new
   ↓
deduplicate por guid/id
   ↓
ordenar por published desc
   ↓
[:max_items]
   ↓
gerar RSS
   ↓
escrever
   ↓
mark_published(new_articles)