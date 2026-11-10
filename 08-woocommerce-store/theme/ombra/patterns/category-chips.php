<?php
/**
 * Title: Category chips
 * Slug: ombra/category-chips
 * Categories: ombra, woo-commerce
 * Inserter: no
 *
 * Pill links to the product categories, shown above the shop grid.
 *
 * @package Ombra
 */

$ombra_chips = array(
	''                 => __( 'All', 'ombra' ),
	'candles'          => __( 'Candles', 'ombra' ),
	'diffusers-sprays' => __( 'Diffusers + sprays', 'ombra' ),
	'accessories'      => __( 'Accessories', 'ombra' ),
	'gift-sets'        => __( 'Gift sets', 'ombra' ),
);
?>
<!-- wp:group {"align":"wide","className":"ombra-chips","style":{"spacing":{"blockGap":"0.5rem"}},"layout":{"type":"flex","flexWrap":"wrap"}} -->
<div class="wp-block-group alignwide ombra-chips">
<?php
foreach ( $ombra_chips as $ombra_slug => $ombra_label ) :
	$ombra_url     = $ombra_slug ? ombra_category_url( $ombra_slug ) : ombra_shop_url();
	$ombra_current = $ombra_slug ? is_tax( 'product_cat', $ombra_slug ) : ( function_exists( 'is_shop' ) && is_shop() );
	?>
<!-- wp:paragraph {"className":"ombra-chip<?php echo $ombra_current ? ' is-current' : ''; ?>","fontSize":"small"} -->
<p class="ombra-chip<?php echo $ombra_current ? ' is-current' : ''; ?> has-small-font-size"><a href="<?php echo esc_url( $ombra_url ); ?>"<?php echo $ombra_current ? ' aria-current="page"' : ''; ?>><?php echo esc_html( $ombra_label ); ?></a></p>
<!-- /wp:paragraph -->
<?php endforeach; ?>
</div>
<!-- /wp:group -->
