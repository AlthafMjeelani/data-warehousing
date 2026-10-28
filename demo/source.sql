-- Synthetic data only. Both companies deliberately reuse IDs, codes and invoice numbers.
CREATE DATABASE company_a;
CREATE DATABASE company_b;
USE company_a;

CREATE TABLE sales_summary (
    id int PRIMARY KEY, invoice_no varchar(45) UNIQUE NOT NULL, sales_date date,
    customer_code varchar(45), customer_name varchar(100), route_code varchar(45),
    route_name varchar(100), salesman_code varchar(45), salesman_name varchar(100),
    currency_code varchar(10), void int DEFAULT 0, net_amount decimal(18,4),
    modified_at datetime(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
);
CREATE TABLE sales_details (
    id int PRIMARY KEY, detail_code varchar(45) UNIQUE NOT NULL, sales_code varchar(45),
    product_code varchar(45), product_name varchar(100), sales_type varchar(20),
    net_amount decimal(18,4), total_taxable_amount decimal(18,4), tax_amount decimal(18,4),
    multipack_quantity decimal(18,4), multiplier decimal(18,4), cost_price decimal(18,4),
    discount_amount decimal(18,4), base_multipack_code varchar(20),
    modified_at datetime(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
);
CREATE TABLE customer (id int PRIMARY KEY, code varchar(45), name varchar(100));
CREATE TABLE product (
    id int PRIMARY KEY, code varchar(45), name varchar(100), category int, subcategory int
);
CREATE TABLE route (id int PRIMARY KEY, code varchar(45), name varchar(100), branch int);
CREATE TABLE branches (id int PRIMARY KEY, code varchar(45), name varchar(100), area int);
CREATE TABLE area (id int PRIMARY KEY, code varchar(45), name varchar(100), region int);
CREATE TABLE region (id int PRIMARY KEY, code varchar(45), name varchar(100));
CREATE TABLE p_category (id int PRIMARY KEY, code varchar(45), name varchar(100));
CREATE TABLE p_subcategory (id int PRIMARY KEY, code varchar(45), name varchar(100));
CREATE TABLE users (id int PRIMARY KEY, code varchar(45), name varchar(100));

INSERT INTO customer VALUES (1,'C1','Market One'),(2,'C2','Market Two');
INSERT INTO product VALUES (1,'P1','Orange Juice',1,1),(2,'P2','Apple Juice',1,1);
INSERT INTO route VALUES (1,'R1','Central Route',1);
INSERT INTO branches VALUES (1,'B1','Central Branch',1);
INSERT INTO area VALUES (1,'A1','Central Area',1);
INSERT INTO region VALUES (1,'G1','North');
INSERT INTO p_category VALUES (1,'CAT1','Beverages');
INSERT INTO p_subcategory VALUES (1,'SUB1','Juice');
INSERT INTO users VALUES (1,'E1','Demo Salesperson');

INSERT INTO sales_summary(id,invoice_no,sales_date,customer_code,customer_name,route_code,
    route_name,salesman_code,salesman_name,currency_code,void,net_amount) VALUES
(1,'INV001',CURRENT_DATE - INTERVAL 40 DAY,'C1','Market One','R1','Central Route',
    'E1','Demo Salesperson','AED',0,157.5),
(2,'INV002',CURRENT_DATE - INTERVAL 1 DAY,'C2','Market Two','R1','Central Route',
    'E1','Demo Salesperson','AED',0,189),
(3,'INV003',CURRENT_DATE,'C1','Market One','R1','Central Route',
    'E1','Demo Salesperson','AED',1,1050);
INSERT INTO sales_details(id,detail_code,sales_code,product_code,product_name,sales_type,
    net_amount,total_taxable_amount,tax_amount,multipack_quantity,multiplier,cost_price,
    discount_amount,base_multipack_code) VALUES
(1,'L1','INV001','P1','Orange Juice','sales',105,100,5,10,1,6,0,'EA'),
(2,'L2','INV001','P2','Apple Juice','sales',52.5,50,2.5,5,1,6,0,'EA'),
(3,'L3','INV002','P1','Orange Juice','sales',210,200,10,20,1,6,0,'EA'),
(4,'L4','INV002','P1','Orange Juice','gr',21,20,1,2,1,6,0,'EA'),
(5,'L5','INV003','P1','Orange Juice','sales',1050,1000,50,100,1,6,0,'EA');

CREATE TABLE company_b.sales_summary LIKE company_a.sales_summary;
CREATE TABLE company_b.sales_details LIKE company_a.sales_details;
CREATE TABLE company_b.customer LIKE company_a.customer;
CREATE TABLE company_b.product LIKE company_a.product;
CREATE TABLE company_b.route LIKE company_a.route;
CREATE TABLE company_b.branches LIKE company_a.branches;
CREATE TABLE company_b.area LIKE company_a.area;
CREATE TABLE company_b.region LIKE company_a.region;
CREATE TABLE company_b.p_category LIKE company_a.p_category;
CREATE TABLE company_b.p_subcategory LIKE company_a.p_subcategory;
CREATE TABLE company_b.users LIKE company_a.users;
INSERT INTO company_b.sales_summary SELECT * FROM company_a.sales_summary;
INSERT INTO company_b.sales_details SELECT * FROM company_a.sales_details;
INSERT INTO company_b.customer SELECT * FROM company_a.customer;
INSERT INTO company_b.product SELECT * FROM company_a.product;
INSERT INTO company_b.route SELECT * FROM company_a.route;
INSERT INTO company_b.branches SELECT * FROM company_a.branches;
INSERT INTO company_b.area SELECT * FROM company_a.area;
INSERT INTO company_b.region SELECT * FROM company_a.region;
INSERT INTO company_b.p_category SELECT * FROM company_a.p_category;
INSERT INTO company_b.p_subcategory SELECT * FROM company_a.p_subcategory;
INSERT INTO company_b.users SELECT * FROM company_a.users;
UPDATE company_b.sales_summary SET currency_code='SAR';
UPDATE company_b.region SET name='South';
CREATE USER 'warehouse_reader'@'%' IDENTIFIED BY 'demo_reader';
GRANT SELECT ON company_a.* TO 'warehouse_reader'@'%';
GRANT SELECT ON company_b.* TO 'warehouse_reader'@'%';
