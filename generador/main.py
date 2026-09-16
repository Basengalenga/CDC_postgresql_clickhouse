import asyncio
import random
import time
import psycopg
from psycopg_pool import AsyncConnectionPool

# Database configuration - update with your credentials
DSN = "dbname=taqueria_don_puerco user=admin password=admin123 host=postgres port=5432"

# The Taquería Menu
MENU = [
    ("Taco", "Relleno Negro", 25.00), ("Torta", "Relleno Negro", 45.00),
    ("Taco", "Cochinita", 25.00),     ("Torta", "Cochinita", 45.00),
    ("Taco", "Pavo Asado", 30.00),    ("Torta", "Pavo Asado", 50.00),
    ("Taco", "Castacán", 35.00),      ("Torta", "Castacán", 55.00)
]

# In-memory tracking for fast operations without heavy SELECTs
active_orders = []
customer_ids = []
menu_item_ids = []
menu_prices = {}  # {item_id: price} — usado para no hardcodear el precio en el worker

async def setup_database(pool):
    """Initializes schema, customers, and menu items."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Seed Menu Items
            for cat, meat, price in MENU:
                await cur.execute("""
                    INSERT INTO menu_items (name, category, meat_type, current_price)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT DO NOTHING RETURNING item_id;
                """, (f"{cat} de {meat}", cat, meat, price))
                res = await cur.fetchone()
                if res:
                    menu_item_ids.append(res[0])
                    menu_prices[res[0]] = price

            if not menu_item_ids:  # If already populated
                await cur.execute("SELECT item_id, current_price FROM menu_items")
                async for row in cur:
                    menu_item_ids.append(row[0])
                    menu_prices[row[0]] = float(row[1])

            # Seed 1000 Customers
            for i in range(1000):
                await cur.execute("""
                    INSERT INTO customers (name, phone) 
                    VALUES (%s, %s) ON CONFLICT (phone) DO NOTHING RETURNING customer_id
                """, (f"Customer_{i}", f"555-0100-{i:04d}"))
                res = await cur.fetchone()
                if res: customer_ids.append(res[0])
                
            if not customer_ids:
                await cur.execute("SELECT customer_id FROM customers LIMIT 1000")
                customer_ids.extend([row[0] async for row in cur])
                
        await conn.commit()

async def worker(pool, worker_id, stats):
    """Simulates a fast-paced delivery backend worker."""
    global active_orders
    
    while True:
        try:
            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    action = random.random()
                    
                    # 70% chance: INSERT (New Order)
                    if action < 0.70:
                        cust_id = random.choice(customer_ids)
                        # Create Order
                        await cur.execute(
                            "INSERT INTO orders (customer_id, status) VALUES (%s, 'pending') RETURNING order_id",
                            (cust_id,)
                        )
                        order_id = (await cur.fetchone())[0]
                        
                        # Add 1 to 5 random items to the order
                        total = 0
                        for _ in range(random.randint(1, 5)):
                            item_id = random.choice(menu_item_ids)
                            quantity = random.randint(1, 3)
                            price = menu_prices[item_id]  # precio real del menú, ya no hardcodeado

                            await cur.execute("""
                                INSERT INTO order_items (order_id, item_id, quantity, unit_price)
                                VALUES (%s, %s, %s, %s)
                            """, (order_id, item_id, quantity, price))
                            total += (quantity * price)
                        
                        # Update total
                        await cur.execute("UPDATE orders SET total_amount = %s WHERE order_id = %s", (total, order_id))
                        
                        if len(active_orders) < 50000: # Cap memory usage
                            active_orders.append(order_id)
                        stats['inserts'] += 1

                    # 20% chance: UPDATE (Advance Status)
                    elif action < 0.90 and active_orders:
                        order_id = random.choice(active_orders)
                        new_status = random.choice(['preparing', 'delivering', 'completed'])
                        await cur.execute("UPDATE orders SET status = %s WHERE order_id = %s", (new_status, order_id))
                        
                        if new_status == 'completed':
                            active_orders.remove(order_id)
                        stats['updates'] += 1

                    # 10% chance: DELETE (Cancel order)
                    elif active_orders:
                        order_id = random.choice(active_orders)
                        # Cascading delete will wipe order_items automatically
                        await cur.execute("DELETE FROM orders WHERE order_id = %s", (order_id,))
                        active_orders.remove(order_id)
                        stats['deletes'] += 1

                await conn.commit()
                
        except Exception as e:
            # Catch serialization or constraint errors and continue
            pass 

async def monitor(stats):
    """Logs operations per second to the console."""
    start_time = time.time()
    last_total = 0
    while True:
        await asyncio.sleep(1)
        total_ops = stats['inserts'] + stats['updates'] + stats['deletes']
        ops_sec = total_ops - last_total
        last_total = total_ops
        elapsed = int(time.time() - start_time)
        print(f"[{elapsed}s] Speed: {ops_sec} ops/sec | Total Ops: {total_ops} | "
              f"I: {stats['inserts']} U: {stats['updates']} D: {stats['deletes']}")
        
        # Stop at 200,000 operations
        if total_ops >= 200000:
            print("Target of 200,000 operations reached!")
            import os
            os._exit(0)

async def main():
    stats = {'inserts': 0, 'updates': 0, 'deletes': 0}
    
    print("Connecting to database and seeding...")
    # Setup Async Pool for high throughput
    async with AsyncConnectionPool(DSN, min_size=10, max_size=50) as pool:
        await setup_database(pool)
        
        print("Starting traffic generation...")
        # Create 30 concurrent workers to hammer the database
        tasks = [asyncio.create_task(worker(pool, i, stats)) for i in range(30)]
        tasks.append(asyncio.create_task(monitor(stats)))
        
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())