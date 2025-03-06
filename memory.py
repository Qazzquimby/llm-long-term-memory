import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import sqlite3
import numpy as np
from pathlib import Path

from commands import SYSTEM_PROMPT
from conversation import MODEL, Conversation
from embeddings import LocalEmbeddings


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
        self.embedder = LocalEmbeddings()

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

        # Generate summary using the Prompt engine
        summary_prompt = Conversation()
        summary_prompt.add_message(f"""Given this conversation:

        {content}

        1. Provide a concise summary of the key points.
        2. List relevant tags. Consider these existing tags: {', '.join(existing_tags)}
        3. Each tag has a notes page. List any tags that should have their notes page updated.
        
        You can make new tags as needed. Existing tags are: {', '.join(existing_tags)}

        Format your response as:
        Summary: <summary>
        Tags: <comma-separated tags>
        Update Notes: <comma-separated tags>""")
        
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
                prompt = Conversation()
                prompt.add_message(f"""Update the notes page "{page_title}" with new information from this scene:

                Current scene content:
                {content}

                Current scene summary:
                {summary}

                Provide the complete updated content for this notes page.""")
                
                updated_content = prompt.run(MODEL, should_print=False)
                await self.update_notes_page(page_title, updated_content, scene_id)
        
        return scene

    async def get_embedding(self, text: str) -> List[float]:
        return self.embedder.embed(text)

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

        prompt = Conversation().add_message(update_prompt, role="system")
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

    async def search_similar_scenes(self, query_embedding: List[float], n: int = 5) -> List[Scene]:

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
                content=row[3],
                tags=json.loads(row[4]),
                embedding=np.frombuffer(row[5]).tolist() if row[5] else None
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


    async def get_relevant_info(self) -> Dict[str, Any]:
        """Get relevant notes and scenes based on recent conversation"""
        # Combine recent messages into a single text for comparison
        recent_text = " ".join([msg["content"] for msg in self.conversation_history[-3:]])
        
        # Get embedding for recent conversation
        query_embedding = await self.get_embedding(recent_text)
        
        # Search for similar notes and scenes
        similar_notes = await self.search_similar_notes(query_embedding, n=3)
        similar_scenes = await self.search_similar_scenes(query_embedding, n=3)
        
        return {
            "notes_pages": {note.title: note for note in similar_notes},
            "similar_scenes": similar_scenes
        }

    async def process_message(self, message: str, role: str = "user") -> str:
        """Process a message and generate a response using the Prompt engine."""
        # Add message to conversation history
        self.conversation_history.append({"role": role, "content": message})

        if role == "user":
            # Get relevant information
            relevant_info = await self.get_relevant_info()

            
            # Create new prompt with system message
            prompt = Conversation()
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


    async def search_similar_notes(self, query_embedding: List[float], n: int = 3) -> List[NotesPage]:
        """Search for notes pages similar to the query embedding"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Get all notes pages
        c.execute('SELECT * FROM notes_pages')
        pages = []
        
        for row in c.fetchall():
            # Get embedding for notes content
            page_embedding = await self.get_embedding(row[1])  # row[1] is content
            if page_embedding:
                # Calculate cosine similarity
                similarity = np.dot(query_embedding, page_embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(page_embedding)
                )
                pages.append((similarity, row))
        
        # Sort by similarity and get top n
        pages.sort(key=lambda x: x[0], reverse=True)
        top_pages = pages[:n]
        
        # Convert to NotesPage objects
        result = []
        for _, row in top_pages:
            page = NotesPage(
                title=row[0],
                content=row[1],
                last_updated=row[2],
                related_tags=json.loads(row[3]),
                related_scenes=json.loads(row[4])
            )
            result.append(page)
        
        conn.close()
        return result
