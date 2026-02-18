from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class FabricGroup(db.Model):
    """
    Acts as a container for a collection of fabrics.
    Example: 'Premium Wools' or 'Summer Linens'.
    """
    __tablename__ = 'fabric_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # Relationship: Deleting a group will remove all associated fabrics
    fabrics = db.relationship('Fabric', backref='group', cascade="all, delete-orphan", lazy=True)
    # Relationship: Track which products are assigned this fabric group
    products = db.relationship('Product', backref='fabric_group', lazy=True)


class Fabric(db.Model):
    """
    Individual fabric swatches belonging to a specific FabricGroup.
    """
    __tablename__ = 'fabrics'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    image_urls = db.Column(db.String(500))
    
    # Foreign Key to FabricGroup
    fabric_group_id = db.Column(db.Integer, db.ForeignKey('fabric_groups.id'), nullable=False)

    # Relationship: Images of products using this fabric
    product_images = db.relationship('ProductFabricImage', backref='fabric', cascade="all, delete-orphan", lazy=True)


class Product(db.Model):
    """
    A unified table for the entire product tree.
    Handles Roots (Suit), Categories (Lapel), Styles (Notch), and Attributes (Width).
    """
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, default=0.0)
    
    # Hierarchy: Points to the ID of the parent product
    parent_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'))
    
    # UI Metadata: 'root', 'category', 'product', or 'attribute'
    meta_type = db.Column(db.String(50), default='product')
    
    # Configuration: Stores list of active attributes like ["width", "Buttonhole"]
    # Note: Use db.JSON for SQLite/Postgres or db.Text with manual JSON loading
    attributes_list = db.Column(db.JSON, default=[]) 
    
    # Fabric Link: Only populated for 'root' products usually
    fabric_group_id = db.Column(db.Integer, db.ForeignKey('fabric_groups.id'))

    # Attribute Mapping: If this product is an option for a parent's attribute (e.g. "width"), store "width" here.
    attribute_name = db.Column(db.String(100))

    # Recursive Relationship: Allows p.sub_products to return all children
    sub_products = db.relationship(
        'Product', 
        backref=db.backref('parent', remote_side=[id]),
        cascade="all, delete-orphan"
    )

    # Relationship: Images specific to a fabric for this product
    fabric_images = db.relationship('ProductFabricImage', backref='product', cascade="all, delete-orphan", lazy=True)

    def to_dict(self):
        """Helper method to convert model instance to dictionary for JSON responses"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "parent_id": self.parent_id,
            "meta_type": self.meta_type,
            "attributes_list": self.attributes_list,
            "fabric_group_id": self.fabric_group_id,
            "attribute_name": self.attribute_name
        }

class ProductFabricImage(db.Model):
    """
    Links a specific Product and a specific Fabric to an image.
    Example: 'Suit Jacket' in 'Blue Wool' looks like 'blue_suit.jpg'.
    """
    __tablename__ = 'product_fabric_images'
    __table_args__ = (db.UniqueConstraint('product_id', 'fabric_id', name='_product_fabric_uc'),)
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    fabric_id = db.Column(db.Integer, db.ForeignKey('fabrics.id', ondelete='CASCADE'), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)