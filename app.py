from flask import Flask, request, jsonify
from flask_cors import CORS
from models import db, Product, Fabric, FabricGroup, ProductFabricImage
import os
import boto3
from werkzeug.utils import secure_filename
import json
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

app = Flask(__name__)
CORS(app)
database_url = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
app.config['SQLALCHEMY_DATABASE_URI'] = database_url.replace("postgres://", "postgresql://")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# --- S3 CONFIGURATION ---
s3 = None
aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
aws_endpoint = os.environ.get("AWS_ENDPOINT_URL")

# Only initialize S3 if credentials are provided and not placeholders
if aws_access_key and "your_access_key" not in aws_access_key:
    if aws_endpoint and "your_endpoint_url" in aws_endpoint:
        aws_endpoint = None  # Use default AWS endpoint if placeholder

    s3 = boto3.client(
        "s3",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        endpoint_url=aws_endpoint
    )

BUCKET_NAME = os.environ.get("AWS_BUCKET_NAME")

def upload_file(file):
    if not s3 or not file or not BUCKET_NAME or "your_bucket_name" in BUCKET_NAME:
        return None
    filename = secure_filename(file.filename)
    try:
        s3.upload_fileobj(
            file,
            BUCKET_NAME,
            filename,
            ExtraArgs={'ACL': 'public-read', 'ContentType': file.content_type}
        )
        endpoint = os.environ.get("AWS_PUBLIC_URL") or os.environ.get("AWS_ENDPOINT_URL")
        if endpoint:
             return f"{endpoint}/{BUCKET_NAME}/{filename}"
        return f"https://{BUCKET_NAME}.s3.amazonaws.com/{filename}"
    except Exception as e:
        print(f"S3 Upload Error: {e}")
        return None

# --- SYSTEM ENDPOINTS ---
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/init-db', methods=['GET'])
def init_db():
    try:
        db.create_all()
        return jsonify({"status": "Database tables created successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/upload', methods=['POST'])
def upload_endpoint():
    if 'image' not in request.files:
        return jsonify({"error": "No image provided"}), 400
    url = upload_file(request.files['image'])
    if url:
        return jsonify({"url": url}), 200
    return jsonify({"error": "Upload failed"}), 500

def get_presigned_url(file_url):
    if not file_url:
        return None
    try:
        # Extract the filename (key) from the stored URL
        path = urlparse(file_url).path
        filename = path.split('/')[-1]
        return s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': filename},
            ExpiresIn=3600 # URL valid for 1 hour
        )
    except Exception:
        return file_url

# --- FABRIC GROUP CRUD ---
@app.route('/fabric-groups', methods=['GET', 'POST'])
def handle_groups():
    if request.method == 'POST':
        data = request.json
        group = FabricGroup(name=data['name'], description=data.get('description'))
        db.session.add(group)
        db.session.commit()
        return jsonify({"id": group.id, "status": "created"}), 201
    return jsonify([{"id": g.id, "name": g.name} for g in FabricGroup.query.all()])

# --- FABRIC CRUD ---
@app.route('/fabrics', methods=['POST'])
def add_fabric():
    data = request.form if request.form else request.json
    image_url = data.get('image_urls')
    
    if 'image' in request.files:
        url = upload_file(request.files['image'])
        if url:
            image_url = url
            
    fabric = Fabric(name=data['name'], image_urls=image_url, fabric_group_id=data['fabric_group_id'])
    db.session.add(fabric)
    db.session.commit()
    return jsonify({"id": fabric.id, "status": "created"}), 201

# --- PRODUCT FABRIC IMAGE CRUD ---
@app.route('/product-fabric-images', methods=['POST'])
def add_product_fabric_image():
    data = request.form if request.form else request.json
    product_id = data.get('product_id')
    fabric_id = data.get('fabric_id')
    image_url = data.get('image_url')
    
    if 'image' in request.files:
        url = upload_file(request.files['image'])
        if url:
            image_url = url
            
    # Update existing or create new
    pfi = ProductFabricImage.query.filter_by(product_id=product_id, fabric_id=fabric_id).first()
    if not pfi:
        pfi = ProductFabricImage(product_id=product_id, fabric_id=fabric_id, image_url=image_url)
        db.session.add(pfi)
    else:
        pfi.image_url = image_url
    
    db.session.commit()
    return jsonify({"id": pfi.id, "status": "saved", "image_url": pfi.image_url}), 201

# --- PRODUCT CRUD ---
@app.route('/products', methods=['POST'])
def create_product():
    data = request.form if request.form else request.json

    attributes = data.get('attributes_list', [])
    if isinstance(attributes, str):
        try:
            attributes = json.loads(attributes)
        except:
            attributes = []

    product = Product(
        name=data['name'],
        description=data.get('description'),
        parent_id=data.get('parent_id'),
        meta_type=data.get('meta_type', 'product'),
        attributes_list=attributes,
        fabric_group_id=data.get('fabric_group_id'),
        attribute_name=data.get('attribute_name'),
        price=data.get('price', 0)
    )
    db.session.add(product)
    db.session.commit()
    return jsonify({"id": product.id, "status": "created"}), 201

@app.route('/products/<int:id>', methods=['PUT', 'DELETE'])
def update_delete_product(id):
    product = Product.query.get_or_404(id)
    if request.method == 'DELETE':
        # Recursively delete children first to satisfy Foreign Key constraints
        def delete_recursive(item):
            children = list(item.sub_products) # Create list copy to safely iterate
            for child in children:
                delete_recursive(child)
            db.session.delete(item)
            
        delete_recursive(product)
        db.session.commit()
        return jsonify({"msg": "Deleted"})
    
    data = request.form if request.form else request.json
    
    for key in ['name', 'description', 'parent_id', 'meta_type', 'attributes_list', 'fabric_group_id', 'attribute_name', 'price']:
        if key in data:
            val = data[key]
            if key == 'attributes_list' and isinstance(val, str):
                try:
                    val = json.loads(val)
                except:
                    pass
            setattr(product, key, val)
    
    db.session.commit()
    return jsonify({"msg": "Updated", "id": product.id})

@app.route('/products/tree', methods=['GET'])
def get_tree():
    try:
        def build_node(p):
            node = {
                "id": p.id, "name": p.name, "meta_type": p.meta_type,
                "attributes": p.attributes_list or [], "fabric_group_id": p.fabric_group_id,
                "price": p.price
            }
            
            if p.fabric_group:
                node["fabrics"] = [{"id": f.id, "name": f.name, "image_urls": get_presigned_url(f.image_urls)} for f in p.fabric_group.fabrics]

            # Include fabric-specific images for this product
            node["fabric_images"] = {
                img.fabric_id: get_presigned_url(img.image_url) 
                for img in p.fabric_images
            }

            sub_products = []
            for child in p.sub_products:
                child_node = build_node(child)
                if child.attribute_name:
                    if child.attribute_name not in node:
                        node[child.attribute_name] = []
                    node[child.attribute_name].append(child_node)
                else:
                    sub_products.append(child_node)
            node["sub_products"] = sub_products
            return node

        roots = Product.query.filter_by(parent_id=None).all()
        return jsonify([build_node(r) for r in roots])
    except Exception as e:
        print(f"Tree Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/products/tree', methods=['PUT'])
def update_product_tree():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    if isinstance(data, dict):
        data = [data]

    def update_recursive(node, parent_id=None):
        # Determine ID
        p_id = node.get('id')
        product = None
        if p_id:
            product = Product.query.get(p_id)
        
        if not product:
            product = Product()
            db.session.add(product)
        
        # Update direct fields
        fields = ['name', 'description', 'price', 'meta_type', 'attribute_name', 'fabric_group_id']
        for field in fields:
            if field in node:
                setattr(product, field, node[field])
        
        # Handle attributes list
        if 'attributes' in node:
            product.attributes_list = node['attributes']
        elif 'attributes_list' in node:
            product.attributes_list = node['attributes_list']
            
        product.parent_id = parent_id
        db.session.flush() # Generate ID for new records

        # Update fabric-specific images
        if 'fabric_images' in node and isinstance(node['fabric_images'], dict):
            for fab_id, img_url in node['fabric_images'].items():
                if img_url:
                    pfi = ProductFabricImage.query.filter_by(product_id=product.id, fabric_id=int(fab_id)).first()
                    if pfi:
                        pfi.image_url = img_url
                    else:
                        pfi = ProductFabricImage(product_id=product.id, fabric_id=int(fab_id), image_url=img_url)
                        db.session.add(pfi)

        # Gather children from 'sub_products' and dynamic attribute keys
        children = []
        if 'sub_products' in node and isinstance(node['sub_products'], list):
            children.extend(node['sub_products'])
            
        # Check dynamic attribute keys based on the product's attributes
        attrs = product.attributes_list
        if isinstance(attrs, str):
            try: attrs = json.loads(attrs)
            except: attrs = []
            
        if attrs and isinstance(attrs, list):
            for attr in attrs:
                if attr in node and isinstance(node[attr], list):
                    children.extend(node[attr])
        
        # Recurse
        for child in children:
            update_recursive(child, product.id)

    try:
        for root in data:
            update_recursive(root, None)
        db.session.commit()
        return jsonify({"status": "updated"}), 200
    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({"error": str(e)}), 500

@app.route('/fabric-groups/<int:id>/fabrics', methods=['GET'])
def get_group_fabrics(id):
    group = FabricGroup.query.get_or_404(id)
    return jsonify([{"id": f.id, "name": f.name, "image_urls": get_presigned_url(f.image_urls)} for f in group.fabrics]) 

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)