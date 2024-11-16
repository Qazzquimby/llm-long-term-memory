import json
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass
import sqlite3
import numpy as np
from pathlib import Path
import tiktoken

from core import MODEL, Prompt


@dataclass
class Scene:
    id: str
    timestamp: str
    summary: str
    content: str
    tags: List[str]
    embedding: Optional[List[float]] = None


@dataclass
class NotesPage:
    title: str
    content: str
    last_updated: str
    related_tags: List[str]
    related_scenes: List[str]


class MemorySystem:
    def __init__(self, db_path: str = "memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self.setup_database()
        self.current_scene = None
        self.conversation_history = []

    def setup_database(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS scenes (
                id TEXT PRIMARY KEY,
                timestamp TEXT,
                summary TEXT,
                content TEXT,
                tags TEXT,
                embedding BLOB
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS notes_pages (
                title TEXT PRIMARY KEY,
                content TEXT,
                last_updated TEXT,
                related_tags TEXT,
                related_scenes TEXT
            )
        ''')

        conn.commit()
        conn.close()

    async def create_scene(self, content: str, title: str = None, tags: List[str] = None) -> Scene:
        timestamp = datetime.now().isoformat()
        scene_id = f"scene_{timestamp}"
        
        # Generate summary using the Prompt engine
        prompt = Prompt()
        prompt.add_message(f"""Summarize the key points you want to remember:

        {content}
        
        Summary:""")
        summary = prompt.run(MODEL, should_print=False)
        
        scene = Scene(
            id=scene_id,
            timestamp=timestamp,
            summary=summary,
            content=content,
            tags=tags or [],
            embedding=None  # We'll add embedding support later
        )
        
        self._save_scene(scene)
        return scene

    # async def get_embedding(self, text: str) -> List[float]:
    #     # Get embedding using your preferred embedding model
    #     # This is a placeholder - you'd want to use a real embedding service
    #     response = await completion(
    #         model="text-embedding-ada-002",
    #         messages=[{"role": "user", "content": text}]
    #     )
    #     return response.data[0].embedding

    def _save_scene(self, scene: Scene):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            INSERT OR REPLACE INTO scenes
            (id, timestamp, summary, content, tags, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            scene.id,
            scene.timestamp,
            scene.summary,
            scene.content,
            json.dumps(scene.tags),
            np.array(scene.embedding).tobytes() if scene.embedding else None
        ))

        conn.commit()
        conn.close()

    async def update_notes_page(self, title: str, new_content: str, scene_id: str):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Get existing page if it exists
        c.execute('SELECT * FROM notes_pages WHERE title = ?', (title,))
        result = c.fetchone()

        if result:
            page_data = {
                'title': result[0],
                'content': result[1],
                'last_updated': result[2],
                'related_tags': json.loads(result[3]),
                'related_scenes': json.loads(result[4])
            }
        else:
            page_data = {
                'title': title,
                'content': '',
                'last_updated': datetime.now().isoformat(),
                'related_tags': [],
                'related_scenes': []
            }

        # Generate updated content using LLM
        update_prompt = f"""Given the following new information about {title}:

        {new_content}

        And the existing notes entry:

        {page_data['content']}

        Please provide an updated notes entry that incorporates the new information while maintaining existing relevant details."""

        update_response = await completion(
            model="gpt-4",
            messages=[{"role": "user", "content": update_prompt}]
        )

        updated_content = update_response.choices[0].message.content

        # Update page data
        page_data['content'] = updated_content
        page_data['last_updated'] = datetime.now().isoformat()
        page_data['related_scenes'] = list(
            set(page_data['related_scenes'] + [scene_id]))

        # Save to database
        c.execute('''
            INSERT OR REPLACE INTO notes_pages
            (title, content, last_updated, related_tags, related_scenes)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            title,
            updated_content,
            page_data['last_updated'],
            json.dumps(page_data['related_tags']),
            json.dumps(page_data['related_scenes'])
        ))

        conn.commit()
        conn.close()

    async def search_similar_scenes(self, query: str, n: int = 5) -> List[Scene]:
        # Get embedding for query
        query_embedding = await self.get_embedding(query)

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Get all scenes
        c.execute('SELECT * FROM scenes')
        scenes = []

        for row in c.fetchall():
            embedding = np.frombuffer(row[6]) if row[6] else None
            if embedding is not None:
                # Calculate cosine similarity
                similarity = np.dot(query_embedding, embedding) / (
                        np.linalg.norm(query_embedding) * np.linalg.norm(embedding)
                )
                scenes.append((similarity, row))

        # Sort by similarity and get top n
        scenes.sort(key=lambda x: x[0], reverse=True)
        top_scenes = scenes[:n]

        # Convert to Scene objects
        result = []
        for _, row in top_scenes:
            scene = Scene(
                id=row[0],
                timestamp=row[1],
                summary=row[2],
                raw_content=row[3],
                characters=json.loads(row[4]),
                tags=json.loads(row[5]),
                embedding=np.frombuffer(row[6]).tolist() if row[6] else None
            )
            result.append(scene)

        conn.close()
        return result

    def get_notes_page(self, title: str) -> Optional[NotesPage]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('SELECT * FROM notes_pages WHERE title = ?', (title,))
        result = c.fetchone()

        if result:
            page = NotesPage(
                title=result[0],
                content=result[1],
                last_updated=result[2],
                related_tags=json.loads(result[3]),
                related_scenes=json.loads(result[4])
            )
            conn.close()
            return page

        conn.close()
        return None


    async def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract entities (characters, locations, items) from text."""
        prompt = f"""Extract entities from the following text, categorized by type:

        Text: {text}

        Return as JSON with categories:
        - characters
        - locations
        - items
        - concepts"""

        response = await completion(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )

        return json.loads(response.choices[0].message.content)

    async def get_relevant_info(self, message: str) -> Dict[str, Any]:
        """Get all relevant information for a message."""
        # Extract entities
        entities = await self.extract_entities(message)

        # Get notes pages for all entities
        notes_pages = {}
        for category in entities.values():
            for entity in category:
                page = self.get_notes_page(entity)
                if page:
                    notes_pages[entity] = page

        # Get similar scenes
        similar_scenes = await self.search_similar_scenes(message, n=3)

        # Get related entities from notes pages
        related_entities = set()
        for page in notes_pages.values():
            # Extract entities from page content
            page_entities = await self.extract_entities(page.content)
            for category in page_entities.values():
                related_entities.update(category)

        # Get notes pages for related entities
        for entity in related_entities:
            if entity not in notes_pages:
                page = self.get_notes_page(entity)
                if page:
                    notes_pages[entity] = page

        return {
            "notes_pages": notes_pages,
            "similar_scenes": similar_scenes,
            "entities": entities
        }

    async def process_message(self, message: str, role: str = "user") -> str:
        """Process a message and generate a response."""
        # Add message to conversation history
        self.conversation_history.append({"role": role, "content": message})

        # Check for scene change
        if role == "user" and await self.detect_scene_change(message):
            # Create new scene from current conversation
            current_content = "\n".join(
                [m["content"] for m in self.conversation_history])
            entities = await self.extract_entities(current_content)

            self.current_scene = await self.create_scene(
                raw_content=current_content,
                characters=entities["characters"],
                tags=[item for category in entities.values() for item in category]
            )

            # Clear conversation history
            self.conversation_history = []

        if role == "user":
            # Get relevant information
            relevant_info = await self.get_relevant_info(message)

            # Create prompt with context
            context_prompt = "Relevant information:\n\n"

            # Add notes pages
            for title, page in relevant_info["notes_pages"].items():
                context_prompt += f"About {title}:\n{page.content}\n\n"

            # Add similar scenes
            for scene in relevant_info["similar_scenes"]:
                context_prompt += f"Related event:\n{scene.summary}\n\n"

            # Add conversation history
            conversation_context = "\n".join([
                f"{m['role']}: {m['content']}"
                for m in self.conversation_history[-5:]  # Last 5 messages
            ])

            prompt = f"""{context_prompt}

            Recent conversation:
            {conversation_context}

            Respond naturally as an RPG character, incorporating relevant information from memory where appropriate, but without explicitly mentioning the memory system."""

            response = await completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )

            return response.choices[0].message.content


