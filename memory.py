import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import sqlite3
import numpy as np
from pathlib import Path

from commands import SYSTEM_PROMPT
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

    async def create_scene(self, content: str, title: str = None) -> Scene:
        timestamp = datetime.now().isoformat()
        scene_id = f"scene_{timestamp}"
        
        # Get existing tags from database for matching
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT tags FROM scenes')
        existing_tags = set()
        for row in c.fetchall():
            if row[0]:
                existing_tags.update(json.loads(row[0]))
        conn.close()

        # Generate summary and suggest tags using the Prompt engine
        prompt = Prompt()
        prompt.add_message(f"""Given this conversation:

        {content}

        1. Provide a concise summary of the key points.
        2. Suggest appropriate tags. Consider these existing tags: {', '.join(existing_tags)}
        3. List any notes pages that should be updated based on this conversation.

        Format your response as:
        Summary: <summary>
        Tags: <comma-separated tags>
        Update Notes: <comma-separated page titles>""")
        
        response = prompt.run(MODEL, should_print=False)
        
        # Parse response
        parts = response.split('\n')
        summary = parts[0].replace('Summary: ', '').strip()
        tags = [t.strip() for t in parts[1].replace('Tags: ', '').split(',')]
        notes_to_update = [n.strip() for n in parts[2].replace('Update Notes: ', '').split(',')]
        
        scene = Scene(
            id=scene_id,
            timestamp=timestamp,
            summary=summary,
            content=content,
            tags=tags,
            embedding=None
        )
        
        self._save_scene(scene)
        
        # Update each notes page
        for page_title in notes_to_update:
            if page_title:
                prompt = Prompt()
                prompt.add_message(f"""Update the notes page "{page_title}" with new information from this scene:

                Current scene content:
                {content}

                Current scene summary:
                {summary}

                Provide the complete updated content for this notes page.""")
                
                updated_content = prompt.run(MODEL, should_print=False)
                await self.update_notes_page(page_title, updated_content, scene_id)
        
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

        prompt = Prompt().add_message(update_prompt, role="system")
        response = prompt.run(model=MODEL, should_print=False)

        updated_content = response

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
        extract_prompt = f"""Extract entities from the following text, categorized by type:

        Text: {text}

        Return as JSON with categories:
        - characters
        - locations
        - items
        - concepts"""

        prompt = Prompt().add_message(extract_prompt, role="system")

        response = prompt.run(model=MODEL)

        return json.loads(response)

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
        """Process a message and generate a response using the Prompt engine."""
        # Add message to conversation history
        self.conversation_history.append({"role": role, "content": message})

        if role == "user":
            # Get relevant information
            relevant_info = await self.get_relevant_info(message)
            
            # Create new prompt with system message
            prompt = Prompt()
            prompt.add_message(SYSTEM_PROMPT, role="system")
            
            # Add context from notes pages and scenes
            context = []
            
            # Add notes pages
            for title, page in relevant_info["notes_pages"].items():
                context.append(f"notes page - {title}:\n{page.content}")
            
            # Add similar scenes
            for scene in relevant_info["similar_scenes"]:
                context.append(f"Related scene ({scene.timestamp}):\n{scene.summary}")
            
            if context:
                context_message = "Relevant context:\n\n" + "\n\n".join(context)
                prompt.add_message(context_message, role="system")
            
            # Add recent conversation history
            for msg in self.conversation_history[-5:]:
                prompt.add_message(msg["content"], role=msg["role"])
            
            # Get response from LLM
            response = prompt.run(MODEL, should_print=False)
            
            # Process any commands in the response
            if "/scene" in response:
                # Extract scene title if provided
                title = None
                if "/scene " in response:
                    title = response.split("/scene ", 1)[1].split("\n")[0].strip()
                
                # Create new scene from current conversation
                content = "\n".join([m["content"] for m in self.conversation_history])
                await self.create_scene(content=content, title=title)
                self.conversation_history = []

            # Remove command text from response before returning
            clean_response = response
            for cmd in ["/scene", "/search", "/notes"]:
                if cmd in clean_response:
                    parts = clean_response.split(cmd)
                    clean_response = parts[0] + "".join(p.split("\n", 1)[1] if "\n" in p else "" for p in parts[1:])
            
            return clean_response.strip()


