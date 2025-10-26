from neo4j import GraphDatabase

# Change this to your actual Neo4j password (the one you set in Desktop)
URI = "bolt://localhost:7687"
AUTH = ("neo4j", "neo4j123")  # <-- replace with your password

driver = GraphDatabase.driver(URI, auth=AUTH)

try:
    with driver.session() as session:
        result = session.run("RETURN 'Neo4j connection successful!' AS msg")
        print(result.single()["msg"])
finally:
    driver.close()


    