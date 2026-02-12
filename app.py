from flask import Flask, request, jsonify
from flask_cors import CORS
from models import db, Product, Fabric, FabricGroup
import os
import boto3
from werkzeug.utils import secure_filename
import json
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# --- S3 CONFIGURATION ---
s3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    endpoint_url=os.environ.get("AWS_ENDPOINT_URL")
)
BUCKET_NAME = os.environ.get("AWS_BUCKET_NAME")

def upload_file(file):
    if not file or not BUCKET_NAME:
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

# --- PRODUCT CRUD ---
@app.route('/products', methods=['POST'])
def create_product():
    data = request.form if request.form else request.json
    image_url = data.get('image_urls')

    if 'image' in request.files:
        url = upload_file(request.files['image'])
        if url:
            image_url = url

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
        price=data.get('price', 0),
        image_urls=image_url
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
    
    if 'image' in request.files:
        url = upload_file(request.files['image'])
        if url:
            product.image_urls = url

    for key in ['name', 'description', 'parent_id', 'meta_type', 'attributes_list', 'fabric_group_id', 'attribute_name', 'price', 'image_urls']:
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
    def build_node(p):
        node = {
            "id": p.id, "name": p.name, "meta_type": p.meta_type,
            "attributes": p.attributes_list or [], "fabric_group_id": p.fabric_group_id,
            "price": p.price, "image_urls": get_presigned_url(p.image_urls)
        }
        
        if p.fabric_group:
            node["fabrics"] = [{"id": f.id, "name": f.name, "image_urls": get_presigned_url(f.image_urls)} for f in p.fabric_group.fabrics]

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

@app.route('/fabric-groups/<int:id>/fabrics', methods=['GET'])
def get_group_fabrics(id):
    group = FabricGroup.query.get_or_404(id)
    return jsonify([{"id": f.id, "name": f.name, "image_urls": get_presigned_url(f.image_urls)} for f in group.fabrics]) 

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)