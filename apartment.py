from dataclasses import dataclass

@dataclass
class Apartment:
    title: str
    price: str
    location: str
    rooms: str
    size: str
    url: str
    source: str
    description: str = ""
    
    def to_dict(self):
        return {
            'title': self.title,
            'price': self.price,
            'location': self.location,
            'rooms': self.rooms,
            'size': self.size,
            'url': self.url,
            'source': self.source,
            'description': self.description
        }
    
    def get_hash(self):
        import hashlib
        content = f"{self.title}{self.price}{self.location}{self.url}"
        return hashlib.md5(content.encode()).hexdigest()
