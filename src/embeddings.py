from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Union
import torch


class LocalEmbeddings:
    """A class for generating text embeddings locally using sentence-transformers."""

    def __init__(
            self,
            model_name: str = "all-MiniLM-L6-v2",
            device: str = None,
            normalize_embeddings: bool = True
    ):
        """
        Initialize the embeddings model.

        Args:
            model_name: Name of the sentence-transformers model to use
            device: Device to run the model on ('cpu', 'cuda', or None for auto-detection)
            normalize_embeddings: Whether to L2-normalize the embeddings
        """
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        self.model = SentenceTransformer(model_name, device=device)
        self.normalize_embeddings = normalize_embeddings

    def embed(self, texts: Union[str, List[str]], batch_size: int = 32) -> np.ndarray:
        """
        Generate embeddings for the input texts.

        Args:
            texts: Single text or list of texts to embed
            batch_size: Number of texts to process at once

        Returns:
            numpy.ndarray: Array of embeddings
        """
        # Handle single text input
        if isinstance(texts, str):
            texts = [texts]

        # Generate embeddings
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=False
        )

        return embeddings

    def similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            float: Cosine similarity score
        """
        return float(np.dot(embedding1, embedding2) /
                     (np.linalg.norm(embedding1) * np.linalg.norm(embedding2)))