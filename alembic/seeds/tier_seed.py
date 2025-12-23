"""
Tier Seed Script - Automatically seeds subscription tiers

This script is automatically run after each Alembic migration to ensure
tier data exists in the database.

The script is idempotent - it checks for existing data before inserting,
so it's safe to run multiple times.
"""
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.engine import Connection
import logging

logger = logging.getLogger(__name__)


def seed_tier_data(connection: Connection) -> None:
    """
    Seed subscription tiers into the database.

    This function is idempotent - it checks if data exists before inserting.
    Safe to run multiple times.

    Args:
        connection: SQLAlchemy connection object
    """
    try:
        # Check if tier table exists
        table_exists = connection.execute(
            text(
                """
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_name = 'tier'
                """
            )
        ).scalar()

        if not table_exists:
            logger.info("Tier table does not exist yet. Skipping seed.")
            return

        # Check if tiers already exist
        existing_tiers = connection.execute(
            text("SELECT COUNT(*) FROM tier")
        ).scalar()

        # Check if existing tiers have billing data (non-zero prices or stripe_price_id)
        tiers_with_billing = connection.execute(
            text("SELECT COUNT(*) FROM tier WHERE price > 0 OR stripe_price_id IS NOT NULL")
        ).scalar()

        if existing_tiers > 0 and tiers_with_billing > 0:
            logger.info(f"Tier data already seeded ({existing_tiers} tiers with billing data found). Skipping.")
            return

        # Define tier data mapping (name -> data)
        tiers_data_map = {
            "Free": {
                "price": 0,  # $0.00
                "billing_cycle": "MONTHLY",
                "features": {
                    "max_users": 3,
                    "max_products": 50,
                    "max_clients": 100,
                    "support": "Community",
                    "features": ["Basic CRM", "Dashboard", "Reports"]
                },
                "stripe_price_id": None,
                "is_active": True
            },
            "Trial": {
                "price": 0,  # $0.00
                "billing_cycle": "MONTHLY",
                "features": {
                    "max_users": 5,
                    "max_products": 100,
                    "max_clients": 200,
                    "support": "Email",
                    "trial_days": 14,
                    "features": ["Full CRM", "Dashboard", "Advanced Reports", "API Access"]
                },
                "stripe_price_id": None,
                "is_active": True
            },
            "Basic": {
                "price": 1999,  # $19.99
                "billing_cycle": "MONTHLY",
                "features": {
                    "max_users": 10,
                    "max_products": 200,
                    "max_clients": 500,
                    "support": "Email",
                    "features": ["Full CRM", "Dashboard", "Advanced Reports", "API Access", "Integrations"]
                },
                "stripe_price_id": "price_basic_monthly",  # Mock Stripe price ID
                "is_active": True
            },
            "Premium": {
                "price": 9999,  # $99.99
                "billing_cycle": "MONTHLY",
                "features": {
                    "max_users": -1,  # Unlimited
                    "max_products": -1,  # Unlimited
                    "max_clients": -1,  # Unlimited
                    "support": "Priority",
                    "features": [
                        "Full CRM",
                        "Dashboard",
                        "Advanced Reports",
                        "API Access",
                        "Integrations",
                        "Custom Workflows",
                        "Dedicated Account Manager",
                        "SLA Guarantee"
                    ]
                },
                "stripe_price_id": "price_premium_monthly",  # Mock Stripe price ID
                "is_active": True
            },
            # Handle old tier names
            "Pro": {  # Map to Premium
                "price": 9999,
                "billing_cycle": "MONTHLY",
                "features": {
                    "max_users": -1,
                    "max_products": -1,
                    "max_clients": -1,
                    "support": "Priority",
                    "features": ["Full CRM", "Dashboard", "Advanced Reports", "API Access", "Integrations", "Custom Workflows"]
                },
                "stripe_price_id": "price_premium_monthly",
                "is_active": True
            },
            "Enterprise": {  # Keep Enterprise tier
                "price": 19999,  # $199.99
                "billing_cycle": "MONTHLY",
                "features": {
                    "max_users": -1,
                    "max_products": -1,
                    "max_clients": -1,
                    "support": "Dedicated",
                    "features": ["Full CRM", "Dashboard", "Advanced Reports", "API Access", "Integrations", "Custom Workflows", "White Label", "SLA Guarantee"]
                },
                "stripe_price_id": "price_enterprise_monthly",
                "is_active": True
            }
        }

        # If tiers exist but have no billing data, update them
        if existing_tiers > 0:
            logger.info(f"Found {existing_tiers} tiers with default billing data. Updating with proper data...")

            # Get existing tiers
            existing_tier_rows = connection.execute(
                text("SELECT id, name FROM tier")
            ).fetchall()

            updated_count = 0
            for tier_row in existing_tier_rows:
                tier_id = tier_row[0]
                tier_name = tier_row[1]

                if tier_name in tiers_data_map:
                    tier_data = tiers_data_map[tier_name]
                    connection.execute(
                        text(
                            "UPDATE tier SET "
                            "price = :price, "
                            "billing_cycle = :billing_cycle, "
                            "features = :features, "
                            "stripe_price_id = :stripe_price_id, "
                            "is_active = :is_active "
                            "WHERE id = :tier_id"
                        ),
                        {
                            'tier_id': tier_id,
                            'price': tier_data['price'],
                            'billing_cycle': tier_data['billing_cycle'],
                            'features': str(tier_data['features']).replace("'", '"'),
                            'stripe_price_id': tier_data['stripe_price_id'],
                            'is_active': tier_data['is_active']
                        }
                    )
                    updated_count += 1
                else:
                    logger.warning(f"Unknown tier '{tier_name}' found - leaving unchanged")

            connection.commit()
            logger.info(f"✓ Updated {updated_count} existing tiers with billing data")
            return

        logger.info("Seeding subscription tiers...")

        # Insert new tiers (only if table was empty)
        tiers_to_insert = ["Free", "Trial", "Basic", "Premium"]
        for tier_name in tiers_to_insert:
            tier_data = tiers_data_map[tier_name]
            connection.execute(
                text(
                    "INSERT INTO tier (created_at, name, price, billing_cycle, features, stripe_price_id, is_active) "
                    "VALUES (:created_at, :name, :price, :billing_cycle, :features, :stripe_price_id, :is_active)"
                ),
                {
                    'created_at': datetime.utcnow(),
                    'name': tier_name,
                    'price': tier_data['price'],
                    'billing_cycle': tier_data['billing_cycle'],
                    'features': str(tier_data['features']).replace("'", '"'),
                    'stripe_price_id': tier_data['stripe_price_id'],
                    'is_active': tier_data['is_active']
                }
            )

        connection.commit()
        logger.info(f"✓ Seeded {len(tiers_to_insert)} subscription tiers")
        logger.info("✓ Tier seed completed successfully!")

    except Exception as e:
        logger.error(f"Error seeding tier data: {e}")
        raise
